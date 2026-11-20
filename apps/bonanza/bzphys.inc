; bzphys.inc - BONANZA's physics (SPEC.md 130.10.7 as wave 2 changes it,
; 130.11.8; 130.10.8; wave 3's props, 130.12.6): the ball in GROUND units on
; the course part's BZG1 grid, one step a FASTTICK sub-tick.
; tools/bbcourse.py's Physics class is the
; reference and this is integer-exact to it, step for step; SPEC.md 130.11.8.2
; is the binding order both follow.
;
; =============================================================================
; GUEST STATE A HARNESS READS (130.10.7.1, 130.11.5.2, 130.11.8.1; offsets the
; package segment's)
; =============================================================================
;   bz_gx,bz_gy DWORD  the contact point, gu in 24.8: +0 the fraction, +1 the
;                      integer gu as a WORD (0 .. 4,095), +3 zero
;   bz_gz       DWORD  the ball's bottom, px in 24.8, SIGNED: +1 a signed word,
;                      +3 its sign (so the DWORD is the two's complement value)
;   bz_gvx,bz_gvy word 1/256 gu a step;  bz_gvz word 1/256 px a step, up +
;   bz_air      byte   1 while airborne
;   bz_ztop     word   the highest z (px, floor) of this flight
;   bz_lfall    word   the last landing's drop, ztop - h (px, >= 0)
;   bz_lvz      word   the last landing's impact RELATIVE TO THE FLOOR,
;                      max(0, fr - gvz) (130.11.8.5)
;   bz_safe     2 bytes the last SAFE cell stood on: wx, then wy
;   bz_nstep    DWORD  steps since the play began
;   bz_nfall    word   respawns;  bz_nland word landings (every contact)
;   bz_nbnc, bz_nstun, bz_nshat, bz_nhop  words: bounces, stuns, shatters,
;                      Hops this play (130.11.5.2)
;   bz_gh       word   the floor's h4 under an airborne ball over a FLOOR or
;                      GOAL cell; bz_ghv byte 1 when it is valid (130.11.8.1)
;   bz_lvl      4 bytes the arrows' ramp levels 0 .. 8, BZ_K_* order (L R U D)
;   bz_hopw     byte   the Hop's window, steps left
;   bz_bgr      byte   wave 6b (130.17.4.5): the boost's LATE GRACE, steps
;                      left (0 none); it and bz_hopw count down as one word
;   bz_mst      byte   0 none, 1 STUNNED, 2 SHATTERING;  bz_mct its steps left
;   bz_sqf      byte   the squash's steps left (130.11.9.3)
;   bz_kprev    byte   the last step's key byte
;   bz_goal     byte   1 once a step ends with the centre on a GOAL cell, in
;                      play or a replay (not the benchmark), grounded or not
;   bz_nwin     2 bytes the window's centre cell: wx, then wy.  A harness that
;                      POKES the ball's position need not touch it: it sets
;                      bz_pokd to 1, and the next step starts by refilling the
;                      window round the ball's cell and clearing bz_pokd
;                      (bz_wgx, bz_wgy are 16 wx, 16 wy, step 4's cell test)
;   bz_pokd     byte   1: the ball was POKED since the last step (the harness's)
;   bz_nbr      36 bytes the 3 x 3 cells round it, row-major by wy then wx,
;                      each the grid's 4 bytes (OPEN outside the grid)
;   bz_sb       word   the ball's cell row s_b = (gx >> 4) + (gy >> 4), whole gu
;                      (the occluder rule's and the idle test's, 130.10.8):
;                      written ONCE A FRAME, by bz_camera, not by the step
;   bz_resp     byte   1 when this FRAME's steps included a respawn (the cut)
;   bz_mat      byte   (bonanza.asm) the material; bz_pinit copies its BZ_MATTAB
;                      record into bz_mrec, and the step reads it there
;
; Wave 3's (SPEC.md 130.12.6.6; bbcourse.Physics's state3, compared at every
; frame by bonanzaphys):
;   bz_ps       byte   bit 0 bz_wol not empty, bit 1 in a tube, bit 2 carried,
;                      bit 3 a SPLIT cell in the window (SPEC.md 130.24.7.6, D3)
;   bz_wol      19 bytes the window's OBS cells: a count, then (cell 0 - 8,
;                      prop index) pairs in bz_wrt's order (bytes past the
;                      count's pairs are stale)
;   bz_tube     byte   the tube in transit, its index + 1 (0 none); bz_tseg
;                      byte its segment; bz_tcnt word the steps left in it;
;                      bz_tsin word the entry speed
;   bz_onp      byte   carried by the platform: its index + 1, 0 none
;   bz_pkick    16 words each prop's last kick step (0FFFAh: never)
;   bz_nkick, bz_nknock, bz_ntube words: kicks, knock-backs, captures
; Wave 6's and 6b's (130.16.4.3, 130.17.4.3; state6, compared at every frame):
;   bz_btok     byte   the boost's TOKEN: 0, 1 a ground Hop or (round 3) a
;                      fall in flight, 2 that flight ARMED by a second Space
;                      edge (6b)
;   bz_stf      byte   the STRETCH's steps left;  bz_nboost word boosts
;   bz_drx, bz_dry bytes the fractional drag's remainders
;   bz_bgd      word   6b: BOOST less the rebound's gvz where the late grace
;                      opened (bz_bgr above holds its steps left)
;   bz_bsp      byte   round 3b (130.17.17): the boost SPENT, 1 from a boost
;                      until the ball is next on the ground; a launch out of
;                      the air takes the token only while it is 0
;   bz_zoff     word   round 3 (130.17.16): the take-off's z (px), the held
;                      arming's gate; not compared (read under the token 1
;                      only, which is set only where bz_toff writes it)
; and, the step's own (not the model's): bz_wcen, bz_wckd, bz_wbmp, bz_wkd
; (bz_wolf's centre prop, kinds and bumper count), bz_pcn/pcs/pcv (bz_ppos's
; cache), bz_cdd, bz_pdoor, bz_pdi, bz_fslab, bz_fair, bz_fnl.
;
; The SCREEN state 130.10.8 derives at the end of every step: bz_bx, bz_by
; (24.8, the ball's picture top-left) and bz_vx, bz_vy (how far they moved
; this step, a respawn's 0) - which the camera, the frame and the boxes read
; as they did in wave 0b.
;
; Every comparison of a floor with the ball is made in QUARTER px (the grid's
; h4) against the ball's 24.8 height floored to quarter px - exact, because
; 64 h4 > T  <=>  h4 > floor(T / 64)  for an integer h4 (BZ_Q64).
; =============================================================================

BZ_KVOID    equ 0               ; a cell's kind (the low nibble of byte +2;
BZ_KFLOOR   equ 1               ; the high nibble is its SURFACE, 130.11.6.2)
BZ_KWALL    equ 2
BZ_KGOAL    equ 3
BZ_FSAFE    equ 1               ; flags (byte +3): a respawn cell
BZ_FOCC     equ 2               ; ...the occluder pass may lay a record
BZ_ZOPEN    equ 80h             ; an OPEN cell's z0 (-128)
BZ_ST_STUN  equ 1               ; bz_mst: the hard landing's own number
BZ_ST_SHAT  equ 2               ; (BZM_HARD), stored as it is
BZN_NW      equ 0               ; bz_nbr: the cell (dx, dy) at 4 (3 (dy + 1) + dx + 1)
BZN_N       equ 4
BZN_NE      equ 8
BZN_W       equ 12
BZN_C       equ 16
BZN_E       equ 20
BZN_SW      equ 24
BZN_S       equ 28
BZN_SE      equ 32
%if BZ_GSL != 4 || BZ_CLIMB != 4
 %error "bzphys.inc multiplies by BZ_GSL and BZ_CLIMB * 4 with shifts: re-derive them"
%endif
%if BZ_ST_STUN != BZ_HARD_STUN || BZ_ST_SHAT != BZ_HARD_SHATTER
 %error "bzphys.inc stores BZM_HARD as bz_mst: the two numberings must agree"
%endif
%if BZ_K_L != 1 || BZ_K_R != 2 || BZ_K_U != 4 || BZ_K_D != 8
 %error "bzphys.inc's ramp walks bz_lvl in the key byte's bit order"
%endif

%macro BZ_PHYS_VARS 0
; the state bz_pinit zeroes, BZ_PHSN bytes from bz_phs (words first)
VAR bz_phs,0
VAR bz_gx,4
VAR bz_gy,4
VAR bz_gz,4
VAR bz_gvx,2
VAR bz_gvy,2
VAR bz_gvz,2
VAR bz_ztop,2
VAR bz_lfall,2
VAR bz_lvz,2
VAR bz_nstep,4
VAR bz_nfall,2
VAR bz_nland,2
VAR bz_nbnc,2                   ; wave 2's counters (130.11.5.2): bz_nshat
VAR bz_nstun,2                  ; MUST follow bz_nstun (bz_step's .hard)
VAR bz_nshat,2
VAR bz_nhop,2
VAR bz_pkick,2 * BZ_PROPMAX     ; wave 3 (SPEC.md 130.12.6.6): each prop's last
                                ; kick step (a bumper's), 0FFFAh at the start;
                                ; the post's LIT time is the display's (frames
                                ; on the glass, bzwheel.inc's bz_lhold,
                                ; 130.12.6.3) and physics never reads it
VAR bz_gh,2
VAR bz_sb,2
VAR bz_air,1
VAR bz_goal,1
VAR bz_tout,1                   ; wave 7 (130.18.4): 1 when the limit's last step
                                ; timed the play out (the frame loop reads it and
                                ; bz_goal as one word: keep the order)
VAR bz_resp,1
VAR bz_pokd,1                   ; a harness sets it after POKING the ball (the
                                ; next step refills the window, then clears it)
VAR bz_fref,1                   ; wave 9 (130.25.6.3): a family hook's REFILL REQUEST -
                                ; the step's head tests it with bz_pokd as one word
VAR bz_lvl,4                    ; a RESPAWN zeroes bz_lvl .. bz_ghv, 10 bytes
VAR bz_bgr,1                    ; (bz_step's .respawn writes them as five words,
VAR bz_hopw,1                   ; step 1 counts bz_bgr and bz_hopw down as one,
VAR bz_mst,1                    ; bz_capture zeroes bz_sqf and bz_ghv as one:
                                ; keep the order)
VAR bz_mct,1
VAR bz_sqf,1
VAR bz_ghv,1
VAR bz_kprev,1
VAR bz_tcnt,2                   ; wave 3's state (SPEC.md 130.12.6.6): the steps
VAR bz_tsin,2                   ; left in the tube's segment, the entry speed,
VAR bz_nkick,2                  ; and the kicks, knock-backs and captures this
VAR bz_nknock,2                 ; play
VAR bz_ntube,2
VAR bz_pcv,2                    ; bz_ppos's cache: the last (record, n) it
VAR bz_pcs,2                    ; answered and its pos (a pure function of the
VAR bz_pcn,2                    ; two; 0: none)
VAR bz_wol,19                   ; the window's OBS cells, a count and nine
                                ; (cell 0 - 8, prop index) pairs (130.12.3.2)
VAR bz_ps,1                     ; ...bit 0 bz_wol not empty, 1 in a tube, 2 carried
VAR bz_tube,1                   ; ...the tube in transit: index + 1, 0 none
VAR bz_tseg,1                   ; ...its segment
VAR bz_onp,1                    ; ...carried by the platform: its index + 1, 0 none
VAR bz_wcen,1                   ; bz_wolf's own: the centre cell's prop (index +
VAR bz_wckd,1                   ; 1, 0 none) and its kind, the bumpers on bz_wol,
VAR bz_wbmp,1                   ; and each pair's prop's kind - read by the step
VAR bz_wkd,9                    ; instead of the records (not the model's state)
VAR bz_nckpt,2                  ; wave 4 (SPEC.md 130.14.4.7): flags first
VAR bz_npad,2                   ; touched, pad swaps, lip-outs, spring launches
VAR bz_nlip,2                   ; and RETURNs this play - physics' own, compared
VAR bz_nspr,2                   ; with the model and read by the sound (130.14.10)
VAR bz_nret,2
VAR bz_nboost,2                 ; wave 6 (SPEC.md 130.16.4.3): boosts this play
VAR bz_bgd,2                    ; wave 6b (130.17.4.5): BOOST less the rebound's
                                ; gvz, written where the grace opens (never cleared)
VAR bz_ckpt,1                   ; ...the last flag touched + 1 (0: none, the start)
VAR bz_ckmat,1                  ; ...the ball a respawn gets (the start's, then
                                ; the last flag's record +17)
VAR bz_cksn,1                   ; ...the flags touched, a bit each (their lanes'
                                ; TRUE pose, bzwheel.inc bz_ltrue)
VAR bz_inmo,1                   ; ...1 while the centre is in the cup's mouth
VAR bz_hid,1                    ; ...1 once the ball has HOLED OUT (not drawn)
VAR bz_gfl,1                    ; ...the course's BZG1 FLAGS (bz_pinit's copy)
VAR bz_btok,1                   ; wave 6 (130.16.4.3): the boost's TOKEN, 1 set
VAR bz_stf,1                    ; by a Hop from the ground, 2 that flight ARMED
VAR bz_drx,1                    ; (6b, 130.17.4.2); the STRETCH's steps left;
VAR bz_dry,1                    ; the fractional drag's REMAINDERS, gvx's and
                                ; gvy's (130.16.3.1).  A RESPAWN zeroes the four
                                ; as two words: keep the order
VAR bz_bsp,1                    ; round 3b (130.17.17): 1 from a boost until the
                                ; ball is next on the ground, 0 else
VAR bz_exit,1                   ; wave 8b (130.19.4): the finish's EXIT, 0 - 15 -
                                ; a GOAL cell's flags bits 4 - 7, a cup's +27 -
                                ; written with bz_goal (the pair keeps BZ_PHSN even)
VAR bz_tsec,2                   ; wave 7 (130.18.4): the whole seconds LEFT, as the
VAR bz_t55,1                    ; clock shows them (0: no limit), and the steps to
                                ; the next one (BZ_SECSTEPS a second)
VAR bz_rspo,2                   ; SPEC.md 130.23.3: 1 a title demo's RESPAWN cell
                                ; holds bz_safe (no SAFE cell moves it); +1 zero
VAR bz_fcnt,1                   ; wave 8R (130.22.6): a PLAY's FINISH SEQUENCE - the
VAR bz_ffl,1                    ; steps left + 1 (0: none ran; 1: run out), and the flash's
                                ; steps left in its phase (bits 0 - 6) with the
                                ; clock BLANK as bit 7 (bz_fstart, bz_fstep)
VAR bz_psp,1                    ; D3 (SPEC.md 130.24.7.6): 8 while a SPLIT cell is in
                                ; the window (bz_ps bit 3, which bz_psync and the
                                ; step's .pps rebuild from it), else 0
VAR bz_wfl,1                    ; ...bz_wtail's gate: 1 the course has props, 2 a
                                ; split cell (GF_SPLIT), 3 both (bz_pinit's)
VAR bz_vup,2                    ; wave 9 (SPEC.md 130.25.19): what a family adds to
                                ; the cap BZ_VMAXG (bz_gax.clamp; PICKUPS' speed)
VAR bz_nfev,2                   ; ...a family's EVENTS, the PICKUP sound's counter
                                ; (bzs_events: added to its sum, never compared)
VAR bz_wacc,1                   ; ...what it adds to every force table's force
                                ; (bz_ramp: the air's ACC and the surface's A)
VAR bz_cue,1                    ; ...the timed effect's CUE, display only: bit 0
                                ; SPARKLES, bit 1 the last PU_WARN steps' FLASH
VAR bz_fst,BZ_FSTB              ; wave 9 (SPEC.md 130.25.7.2): the per-play STATE bits
VAR bz_fsl,BZ_FAMMAX * BZF_SLOT ; ...and each family's SLOT (both cleared by class:
VAR bz_fpad,((BZ_FSTB + 1) & 1)  ; a play's start here, a respawn bz_frst's)
VAR bz_phe,0
; the rest: written before they are read
VAR bz_fdb,2 * BZ_FDMSK + BZ_BAL_SHDROWS * BZ_BAL_RB ; 8R.11 (130.22.6): THE DISSOLVE's
                                ; copies - the frame's sprite mask, its frame, its
                                ; shadow - dithered (bz_fdis: the blits' source)
VAR bz_okey,2 * BZ_PROPALL      ; 130.19.10: the records' anchors, sorted (bz_obuild)
VAR bz_oidx,BZ_PROPALL          ; ...and each one's record (bz_owner's search)
VAR bz_tdig,3                   ; wave 7 (130.18.5): the clocks' digit poses of
                                ; bz_tsec - units, tens, hundreds (0 blank, 1 + d
                                ; the digit d): bz_tdset's, at bz_pinit and once
                                ; a second
VAR bz_zoff,2                   ; round 3 (130.17.16): the take-off's z, px
                                ; (bz_toff's), read under the token 1 only,
                                ; which only a take-off through bz_toff sets
VAR bz_mrec,BZ_MATREC           ; the material's BZ_MATTAB record (bz_pinit)
VAR bz_se,BZ_SURFREC            ; BZ_SURFTAB's entry for it on the centre's
                                ; surface: force, drag shift, brake, floor e
VAR bz_surf,1                   ; ...that surface (0FFh: none yet, bz_pinit)
VAR bz_dmask,1                  ; ...its drag shift's mask 2^k - 1 (0 on ice):
                                ; bz_surfset's, derived (130.16.3.1)
VAR bz_kstep,1                  ; this step's key byte
VAR bz_ftg,BZ_LVLMAX + 1        ; the arrows' force a level, ground and air
VAR bz_fta,BZ_LVLMAX + 1        ; (130.11.7.1)
VAR bz_safe,2                   ; wx, wy
VAR bz_nwin,2                   ; wx, wy
VAR bz_wgx,2                    ; 16 wx, 16 wy of the window's centre (the cell test)
VAR bz_wgy,2
VAR bz_sgx,4                    ; the step's START ground position (step 3; z
VAR bz_sgy,4                    ; is put back by its gvz)
VAR bz_zq,2                     ; floor(start z / 64) quarter px, + 16 (the climb)
VAR bz_tsx,2                    ; step 2's slopes of C, signed
VAR bz_tsy,2
VAR bz_fr,2                     ; bz_fill's grid row r; its copies of NROWS, KW,
VAR bz_fnr,2                    ; ROWTAB; the centre's k and the rows s +- 1's
VAR bz_fkw,2                    ; first k
VAR bz_frt,2
VAR bz_fka,2
VAR bz_fdp,2
VAR bz_kx,4                     ; (X0 - 8) << 8 and (Y0 - 13) << 8, 24.8: the
VAR bz_ky,4                     ; projection's constants (bz_crshdr)
VAR bz_nbr,36
VAR bz_nbh,144                  ; D3 (SPEC.md 130.24.7.6): each SPLIT cell of bz_nbr's
                                ; records, copied from section D at 16 x its window
                                ; index (a halved cell's two, a quartered one's four)
VAR bz_sor,2                    ; bz_dray: the other ray's beyond record when it
                                ; blocks at K (0 none); bz_sfb 1 when the facing
VAR bz_sfb,1                    ; ray's blocks (no radial corner then), bz_sq the
VAR bz_sq,1                     ; quadrant; bz_dinner's pick and its "straight"
VAR bz_dhc,1
VAR bz_dst,1
VAR bz_dsn,1                    ; 1 while bz_dinner has not taken the step's START
VAR bz_srf,1                    ; bz_swalls: 1 when its inner push refilled the window
VAR bz_srp,2                    ; step 6's record of a split centre (step 8 reads it)
VAR bz_nbp,18                   ; bz_wsplit: each split window cell's record(s) in
                                ; bz_nbh for bz_blocks (FFh: none; the centre FFh FFh)
; the idle test's last frame (bz_mkboxes, 130.10.8 item 2)
VAR bz_osb,2
VAR bz_ozb,2
VAR bz_oair,1
VAR bz_fin,1                    ; 1: the last play reached the goal (the face)
VAR bz_disc,1                   ; 1: this frame is a centred full write (its
                                ; elapsed sub-ticks are discarded, 130.10.8 item 3)
VAR bz_wch,1                    ; step 4: bit 0 the cell's wx changed, bit 1 wy
VAR bz_nprop,1                  ; wave 3: NPROP (bz_pinit; 16 at most) ...
VAR bz_pdoor,1                  ; ...the step's path, 0 wave 2's, and on the prop
VAR bz_pdi,1                    ; path the centre's doorway: 1 none, 2 along -x,
                                ; 3 along -y; and its windmill;
VAR bz_fslab,1                  ; step 6's slab (index + 1, 0 none), the air
VAR bz_fair,1                   ; state step 6 began with
VAR bz_fnl,2                    ; ...and bz_nland then
VAR bz_cdd,2                    ; the carry's displacement this step, 1/256 gu
%if (bz_phe - bz_phs) & 1
 %error "bz_pinit zeroes the state as words: BZ_PHSN must be even"
%endif
%if BZ_CKPTMAX > 8
 %error "bz_cksn holds a course's flags as the bits of a byte"
%endif
%if BZ_PK_CKPT > BZ_PK_PAD || BZ_PK_CKPT > BZ_PK_CUP || BZ_PK_CKPT > BZ_PK_SPRING || BZ_PK_CKPT <= BZ_PK_PLATFORM || BZ_PK_CKPT <= BZ_PK_BUMPER || BZ_PK_CKPT <= BZ_PK_WINDMILL || BZ_PK_CKPT <= BZ_PK_TUBE
 %error "bz_prule tells wave 4's kinds from wave 3's by one compare against BZ_PK_CKPT"
%endif
%if BZ_FK_WINDMILL < BZ_FK0 || BZ_FK_SPRING < BZ_FK0 || BZ_FK_TUBE < BZ_FK0
 %error "story 9.8 (SPEC.md 130.25.20): the families' KEYS (bz_fone's DL) are family kinds"
%endif
%if bz_tout != bz_goal + 1
 %error "bz_t0 and the step loop test bz_goal and bz_tout as one word"
%endif
%if bz_fref != bz_pokd + 1
 %error "bz_step's head tests bz_pokd and bz_fref as one word (SPEC.md 130.25.6.3)"
%endif
%if bz_stf != bz_btok + 1 || bz_drx != bz_btok + 2 || bz_dry != bz_btok + 3
 %error "bz_step's .resp zeroes bz_btok .. bz_dry as two words, bz_land writes bz_btok and bz_stf as one, bz_surfset cuts bz_drx and bz_dry as one"
%endif
%if BZ_SURF_NORMAL != 0 || BZ_SURF_ICE != 1 || BZ_KFLOOR != 1 || BZ_KGOAL != 3 || BZ_KVOID != 0 || BZ_KWALL != 2
 %error "bz_land's FIRM LEVEL test reads a cell's +2 under one mask (0EDh = 01h): re-derive it"
%endif
%if bz_nshat != bz_nstun + 2 || bz_mst != bz_hopw + 1 || bz_mct != bz_hopw + 2 || bz_sqf != bz_hopw + 3 || bz_ghv != bz_hopw + 4 || bz_bgr != bz_lvl + 4 || bz_hopw != bz_bgr + 1
 %error "bz_land, bz_capture and bz_step's .respawn and countdown rely on the order of their variables"
%endif
%endmacro
BZ_PHSN     equ bz_phe - bz_phs

; -----------------------------------------------------------------------------
; bz_pinit - the ball at the course's start (SPEC.md 130.10.7.1, 130.11.5.2):
; the start tile's centre on its floor, at rest, grounded, the window filled,
; every counter and wave 2's state zero, the material's record copied from
; BZ_MATTAB ([bz_mat]) with its air force table, the ground's built for the
; start's surface by bz_fill, and the screen state derived with a zero
; velocity.  DS = ours, [bz_cseg] the course, bz_crshdr run.  Preserves
; nothing.
; -----------------------------------------------------------------------------
bz_pinit:
    push ds
    pop es
    xor ax, ax
    mov di, bz_phs
    mov cx, BZ_PHSN / 2
    rep stosw
%ifdef BZDEV
    cmp byte [bz_mode], 1       ; wave 7 (130.18.4): a play's or a replay's time
    je .nolim                   ; limit, the course's (bz_clims; 0 none: BENCH);
%endif
    cmp byte [bz_xmode], 0      ; (wave 8c, 130.19.8.3: EXPLORE has none)
    jne .nolim
    mov bl, [bz_crs]            ; the benchmark has none
    xor bh, bh
    shl bx, 1
    mov ax, [bz_clims + bx]
    mov [bz_tsec], ax
    mov byte [bz_t55], BZ_SECSTEPS
.nolim:
    call bz_tdset               ; (wave 7: the clocks' first digits)
    mov ax, 0fffah              ; every post starts dark: its last kick -6
    mov di, bz_pkick            ; (bbcourse.Physics's pkick)
    mov cx, BZ_PROPMAX
    rep stosw
    mov al, [bz_mat]            ; the material's record (the step reads it
    mov ah, BZ_MATREC           ; there, not as immediates)
    mul ah
    add ax, bz_mattab
    xchg ax, si
    mov di, bz_mrec
    mov cx, BZ_MATREC / 2
    rep movsw
    mov al, [bz_mrec + BZM_ACC] ; fta[l] = (ACC l + 4) >> 4: half the ramp
    mov di, bz_fta
    mov cl, 4
    call bz_ramp
    mov byte [bz_surf], 0ffh    ; bz_place's fill builds ftg for the start's
    mov es, [bz_cseg]
    mov ax, [es:BZC_PROPOFF]    ; the prop table, which every window refill
    mov [bz_poff], ax           ; scans for its OBS cells' owners (bz_wolf;
    mov al, [es:BZC_NPROP]      ; bz_pread reads it again for the lanes)
    mov [bz_nprop], al
    call bz_obuild              ; (130.19.10: the owners' index, before the
                                ; first refill)
    call bz_flist               ; (130.25.6.10: each family's own records,
    mov es, [bz_cseg]           ; before its RESET walks them)
    mov byte [bz_fwall], 1      ; (every STEP runs at the first step: 130.25.6.11)
    mov ax, BZ_HK_RESET         ; wave 9 (130.25.6.3): the families' RESET, class
    call bz_fall                ; 0 (bz_fst and the slots are zero), before the
                                ; start's refill reads the state (none: no call)
    mov di, [bz_goff]
    mov al, [es:di + BZG_FLAGS] ; wave 4 (130.14.4.2): respawns go to the
    mov [bz_gfl], al            ; last flag on a CKPT course; and the ball a
    mov ah, al                  ; (D3: bz_wtail's gate, bz_wfl: bit 0 props,
    xor al, al                  ; bit 1 a SPLIT cell, GF_SPLIT)
    cmp [bz_nprop], al
    je .wf1
    inc ax
.wf1:
    test ah, BZ_GF_SPLIT
    jz .wf2
    or al, 2
.wf2:
    mov [bz_wfl], al
    mov al, [bz_mat]            ; respawn gets is the one the play STARTED
    mov [bz_ckmat], al          ; with (130.14.18 item 3), until a flag
    mov al, [es:di + BZG_WX]
    mov ah, [es:di + BZG_WY]
    mov [bz_safe], ax           ; bz_safe starts on the start (130.10.4.5)
    call bz_place
%if BZ_TITLE
    cmp byte [bz_tmode], 1      ; SPEC.md 130.23.3: a TITLE DEMO starts from its
    jne .nts                    ; own START BLOCK (bz_tblk), over the start
    call bz_tapply
.nts:
%endif
    call bz_derive
    xor ax, ax
    mov [bz_vx], ax
    mov [bz_vy], ax
    ret

%if BZ_TITLE
; bz_tapply - a title demo's START BLOCK (bz_tblk, SPEC.md 130.23.3) over the
; course's start: its cell placed as a respawn places one (bz_placeat), then
; its position (24.8, three bytes each), velocity and air flag over that, the
; flight's top its height, and its respawn cell held in bz_safe (bz_rspo).
; bbcourse.title_start is the model.  Preserves nothing.
bz_tapply:
    mov cl, 4
    mov ax, [bz_tblk + 1]       ; the cell: gx >> 12, gy >> 12
    shr ax, cl
    mov dx, [bz_tblk + 4]
    shr dx, cl
    mov ah, dl
    call bz_placeat
    mov si, bz_tblk
    mov di, bz_gx
    call .p3
    mov di, bz_gy
    call .p3
    mov di, bz_gz
    call .p3
    lodsw
    mov [bz_gvx], ax
    lodsw
    mov [bz_gvy], ax
    lodsw
    mov [bz_gvz], ax
    lodsb
    mov [bz_air], al
    lodsw                       ; the respawn cell: FFh FFh none
    cmp al, 0ffh
    je .nr
    mov [bz_safe], ax
    mov byte [bz_rspo], 1
.nr:
    mov ax, [bz_gz + 1]
    mov [bz_ztop], ax
    ret
.p3:                            ; three bytes at SI to the dword at DI, its top 0
    lodsw
    mov [di], ax
    lodsb
    cbw
    mov ah, 0
    mov [di + 2], ax
    ret
%endif

; bz_ramp - a force table (130.11.7.1): [DI + l] = ((AL + bz_wacc) l + 4) >> CL
; for the levels l = 0 .. BZ_LVLMAX (CL = 3 the ground's, 4 the air's): bz_wacc
; is a family's raise (wave 9, SPEC.md 130.25.19: PICKUPS' speed; 0 otherwise),
; so a pad's swap or a change of surface under it keeps it.  DS = ours.
; Clobbers AX, BX, CH, DX, DI.
bz_ramp:
    add al, [bz_wacc]
    cbw
    mov dx, 4
    mov ch, BZ_LVLMAX + 1
.l:
    mov bx, dx
    shr bx, cl
    mov [di], bl
    inc di
    add dx, ax
    dec ch
    jnz .l
    ret

; BZ_Q64: DX:AX (signed, 24.8) -> AX = floor(DX:AX / 64), when that fits a
; word: (DX:AX >> 8) << 2 from DL:AH, and the fraction's top two bits.
; Clobbers DX.
%macro BZ_Q64 0
    mov dh, dl
    mov dl, ah                  ; DX = DX:AX >> 8
    shl dx, 1
    shl dx, 1
    rol al, 1
    rol al, 1
    and ax, 3
    or ax, dx
%endmacro

; -----------------------------------------------------------------------------
; bz_step's steps 4 - 6 are written ONCE and run by both paths (SPEC.md
; 130.13.8): wave 2's (no prop in the window) and the PROP path (130.12.6.5),
; told apart by bz_pdoor - 0 on wave 2's path, written at step 4 every step
; that reaches it, and 1 - 3 on the prop path (no doorway, the doorway along
; -x, along -y).  The prop path's own parts sit where they hook in - its
; prefix (the START, the doorway, a drain's capture), the posts and the
; window after the walls, the floor's prop cells, bz_onp - each behind a test
; of bz_pdoor that wave 2's path jumps on and the prop path falls through;
; the doorway's own branch is out of line (bz_step.wdoor, .ndoor).  A ball
; with no prop near pays those four tests (about 133 clk raw a step, 130.13.8)
; and nothing else, and the two paths cannot drift apart.
; -----------------------------------------------------------------------------
; BZ_START: the step's START ground position, for the fallback's undo, from
; the moved one (gx - gvx, gy - gvy).  Clobbers AX, DX.
%macro BZ_START 0
    mov ax, [bz_gvx]
    cwd
    neg dx
    neg ax
    sbb dx, 0
    add ax, [bz_gx]
    adc dx, [bz_gx + 2]
    mov [bz_sgx], ax
    mov [bz_sgx + 2], dx
    mov ax, [bz_gvy]
    cwd
    neg dx
    neg ax
    sbb dx, 0
    add ax, [bz_gy]
    adc dx, [bz_gy + 2]
    mov [bz_sgy], ax
    mov [bz_sgy + 2], dx
%endmacro

; BZ_LVL1: the keyboard's ramp for one arrow (130.11.7.1), its level in the
; byte register %1 and its key BH's bit 0, shifted out: held, up one to
; BZ_LVLMAX; released, down two to 0.
%macro BZ_LVL1 1
    shr bh, 1
    jnc %%rel
    cmp %1, BZ_LVLMAX
    jae %%done
    inc %1
    jmp short %%done
%%rel:
    sub %1, 2
    jnc %%done
    xor %1, %1
%%done:
%endmacro

; -----------------------------------------------------------------------------
; bz_step - ONE STEP, in SPEC.md 130.11.8.2's binding order (the numbers below
; are its steps).  DS = ours.  Preserves CX and ES (the frame loop's count and
; segment) and nothing else.
; -----------------------------------------------------------------------------
bz_step:
    push cx
    push es
    mov es, [bz_cseg]
    cmp word [bz_pokd], 0       ; C: the centre's cell.  The window is centred
    jne .poked                  ; on it already unless a harness POKED the ball
.unpoked:                       ; and said so (bz_pokd: the hot path pays one
                                ; test, not the cell compares), or a family's
                                ; hook asked for a refill (bz_fref, wave 9)
    ; ---- 1. the keys, whatever the ball's state: the key byte K ----
    mov al, [bz_mode]
    cmp al, 1
%ifdef BZDEV
    je .auto
%endif
    ja .replay
    mov bl, [bz_keys]           ; PLAY: the frame's key byte and tilt byte
    mov bh, [bz_tilt]           ; (bz_input),
%ifdef BZDEV
    cmp byte [bz_apilot], 0     ; ...or, under a HARNESS's bz_apilot, the
    jne .apil                   ; autopilot's (SPEC.md 130.14.14 bonanzagame)
.apild:
%endif
    mov [bz_tby], bh
    cmp bl, [bz_rk]             ; RECORDED - the current run extended while
    jne .rec                    ; both are the same and it is under 255 steps
    cmp bh, [bz_rt]             ; (SPEC.md 130.11.12.1, 130.14.8.3), else
    jne .rec                    ; bz_rrec
    cmp byte [bz_rn], 255
    jae .rec
    inc byte [bz_rn]
    jmp short .key
.rec:
    call bz_rrec
    jmp short .key
.replay:
    call bz_rnext               ; a REPLAY: the log's next byte and tilt byte
    jmp short .key
%ifdef BZDEV
.apil:                          ; a play whose key bytes are the autopilot's,
    call bz_auto                ; recorded as a play's: the rows' driver
    mov bh, BZ_TILT_KEYS        ; (out of the hot path: never set by the
    jmp short .apild            ; package itself)
.auto:
    call bz_auto                ; the benchmark: BL = the arrows it would hold -
    mov [bz_kstep], bl          ; never RETURN and never a tilt, so straight to
    mov bh, bl                  ; the keyboard's ramp: no bit-6 test, no tilt
    jmp short .lv               ; byte stored or compared (130.14.12's BENCH
                                ; row; bz_play sets bz_tby to the keyboard's
                                ; once, and only a play or a replay moves it)
%endif
.key:
    test bl, BZ_K_RET           ; wave 4: RETURN (Backspace) first, and the
    jnz .kret                   ; step runs nothing else (130.14.4.5)
.key2:
    mov [bz_kstep], bl
    mov bh, bl                  ; the ramp (130.11.7.1): a held arrow's level
                                ; up one to 8, a released one's down two to 0
    cmp byte [bz_tby], BZ_TILT_KEYS ; a TILT step's caps (130.14.8.2): out of
    jne .tilt                   ; the keyboard's path, which is this compare
.lv:
    mov ax, [bz_lvl]            ; the four levels in AL, AH, DL, DH (L R U D),
    mov dx, [bz_lvl + 2]        ; each by BH's next bit
    BZ_LVL1 al
    BZ_LVL1 ah
    BZ_LVL1 dl
    BZ_LVL1 dh
    mov [bz_lvl], ax
    mov [bz_lvl + 2], dx
.hopw:
    mov al, bl                  ; the Hop's window: Space's key-down EDGE opens
    xchg al, [bz_kprev]         ; it, else it counts down (130.11.7.2)
    not al
    and al, bl
    test al, BZ_K_HOP
    jz .hw
    mov al, [bz_bgr]            ; wave 6b (130.17.4.5): the same edge CONVERTS
    or al, al                   ; an open grace's rebound into the boost ...
    jnz .conv
    mov byte [bz_hopw], BZ_HOPWIN
    cmp byte [bz_btok], 1       ; ...else (130.17.4.2) it ARMS a ground Hop's
    jne .st                     ; flight, the token 1 -> 2 (a Hop's own edge
    inc byte [bz_btok]          ; comes here with the token still 0)
    jmp short .st
.hw:
    mov ax, [bz_bgr]            ; no edge: the window and (6b) the grace count
    or ax, ax                   ; down, AL = bz_bgr and AH = bz_hopw, each to
    jz .st                      ; 0 (the ordinary step's whole cost is this
    cmp al, 1                   ; test, as wave 6's of bz_hopw alone)
    adc al, -1
    cmp ah, 1
    adc ah, -1
    mov [bz_bgr], ax
.st:                            ; ...then the ball's state - none once it has
    cmp byte [bz_hid], 0        ; HOLED OUT: the keys ran, nothing else does
    jne .ptr2                   ; (130.14.18 item 3)
    cmp byte [bz_sqf], 0
    je .sq
    dec byte [bz_sqf]
.sq:
    cmp byte [bz_stf], 0        ; wave 6: the stretch's steps (130.16.4.4)
    je .sf
    dec byte [bz_stf]
.sf:
    mov al, [bz_mst]
    or al, al
    jz .forces
    dec byte [bz_mct]
    jnz .mlive
    mov byte [bz_mst], 0        ; its time is up: none (a stun's end) ...
    cmp al, BZ_ST_SHAT
    jne .forces
    cmp word [bz_goal], 0       ; ...or the shattered ball's RESPAWN - not in
    jne .mkeep                  ; a FINISH SEQUENCE (130.22.6), where it
    jmp .respawn                ; stays in pieces, on its last frame
.mkeep:
    mov [bz_mst], al
    inc byte [bz_mct]
.mlive:
    cmp al, BZ_ST_SHAT          ; a shattering ball does not move
    jne .forces
    jmp .end
.ptr1:                          ; (the short jump's reach)
    jmp .pst
.ptr2:
    jmp .end
.conv:                          ; wave 6b: the LATE GRACE CONVERTS (130.17.4.5)
    mov cx, BZ_BGRACE           ; on the k-th step after its contact (AL =
    sub cl, al                  ; bz_bgr, CX = k - 1 = BZ_BGRACE - AL): gvz +=
    mov ax, [bz_bgd]            ; bgd, and z += bgd for each of the k - 1
    add [bz_gvz], ax            ; steps the rebound has flown, so the ball is
    imul cx                     ; where the contact's boost would have it now
    add [bz_gz], ax
    adc [bz_gz + 2], dx
    mov ax, [bz_gz + 1]         ; ztop = z; the grace and the window closed in
    mov [bz_ztop], ax           ; one word; the boost's own bookkeeping (the
    xor ax, ax                  ; stretch, no squash; the state's countdown
    mov [bz_bgr], ax            ; below leaves bz_stf at BZ_STRS - 1, as a
    mov [bz_sqf], al            ; contact's boost the step after it)
    inc word [bz_nboost]
    mov byte [bz_stf], BZ_STRS
    mov byte [bz_bsp], 1        ; round 3b: spent until the ball is grounded
    jmp .st
    ; ---- 2. forces ----
.forces:
    test byte [bz_ps], 6        ; wave 3 (SPEC.md 130.12.6.5 step 1): in a tube,
    jnz .ptr1                   ; or carried by the platform
.forces2:
    xor di, di                  ; DI, BP = the arrows on (gvx, gvy), each at its
    xor bp, bp                  ; level, pushed along the screen through the
    cmp byte [bz_mst], 0        ; ground (130.10.7.2); none while stunned
    jne .pushed
    mov dl, bl
    mov bx, bz_ftg              ; the ground's force a level, or the air's
    cmp byte [bz_air], 0
    je .k0
    mov bx, bz_fta
.k0:
    test dl, BZ_K_R
    jz .k1
    mov al, [bz_lvl + 1]
    xlat
    cbw
    add di, ax                  ; Right (+F, -F)
    sub bp, ax
.k1:
    test dl, BZ_K_L
    jz .k2
    mov al, [bz_lvl + 0]
    xlat
    cbw
    sub di, ax                  ; Left (-F, +F)
    add bp, ax
.k2:
    test dl, BZ_K_D
    jz .k3
    mov al, [bz_lvl + 3]
    xlat
    cbw
    add di, ax                  ; Down (+F, +F)
    add bp, ax
.k3:
    test dl, BZ_K_U
    jz .pushed
    mov al, [bz_lvl + 2]
    xlat
    cbw
    sub di, ax                  ; Up (-F, -F)
    sub bp, ax
.pushed:
    cmp byte [bz_air], 0
    jne .air
    mov cx, [bz_se + 1]         ; CL = the surface's drag shift (0 none), CH =
    test byte [bz_kstep], BZ_K_GRIP ; its brake, while Grip is held and the
    jz .nogrip                  ; ball is not stunned
    cmp byte [bz_mst], 0
    je .grip
.nogrip:
    xor ch, ch
.grip:
    mov ax, [bz_tsx]            ; gvx += arrows - BZ_GSL sx; drag; brake; clamp
    shl ax, 1                   ; (C's slopes: bz_win9f's, 0 off a plane floor)
    shl ax, 1
    neg ax
    add ax, di
    add ax, [bz_gvx]
    mov si, bz_drx              ; (the drag's remainder for gvx)
    call bz_gax
    mov [bz_gvx], ax
    mov ax, [bz_tsy]            ; gvy the same with sy
    shl ax, 1
    shl ax, 1
    neg ax
    add ax, bp
    add ax, [bz_gvy]
    inc si                      ; (bz_dry: bz_gax keeps SI)
    call bz_gax
    mov [bz_gvy], ax
    call bz_frate               ; gvz: the floor's own rate under the ball
    mov [bz_gvz], ax
    jmp short .move
.air:
                                ; airborne: the arrows at half force, clamped
    mov ax, [bz_gvx]            ; (130.11.7.3); no slope, no drag - bz_gax's
    add ax, di                  ; clamp alone
    call bz_gax.clamp
    mov [bz_gvx], ax
    mov ax, [bz_gvy]
    add ax, bp
    call bz_gax.clamp
    mov [bz_gvy], ax
    mov ax, [bz_gvz]            ; gravity, clamped
    sub ax, BZ_G
    cmp ax, BZ_VZMAX
    jle .g1
    mov ax, BZ_VZMAX
.g1:
    cmp ax, -BZ_VZMAX
    jge .g2
    mov ax, -BZ_VZMAX
.g2:
    mov [bz_gvz], ax
    ; ---- 3. move ----
.move:
    mov ax, [bz_gz + 1]         ; zq = floor(start z / 64) quarter px, plus the
    shl ax, 1                   ; climb in either air state: a neighbour BLOCKS
    shl ax, 1                   ; when its h4 > zq (130.11.8.2 step 5) - BZ_Q64
    mov dl, [bz_gz]             ; from the cells: the whole px << 2, and the
    rol dl, 1                   ; fraction's top two bits
    rol dl, 1
    and dl, 3
    or al, dl
    add ax, BZ_CLIMB * 4        ; (+ 1,024 / 64)
    mov [bz_zq], ax
    mov ax, [bz_gvx]            ; gx += gvx, gy += gvy (the start is kept only
    cwd                         ; when the cell changes, below)
    add [bz_gx], ax
    adc [bz_gx + 2], dx
    mov ax, [bz_gvy]
    cwd
    add [bz_gy], ax
    adc [bz_gy + 2], dx
    cmp byte [bz_air], 0        ; airborne: z += gvz (an undo takes it back)
    je .win
    mov ax, [bz_gvz]
    cwd
    add [bz_gz], ax
    adc [bz_gz + 2], dx
    mov ax, [bz_gz + 1]         ; ztop = max(ztop, z) in whole px
    cmp ax, [bz_ztop]
    jle .win
    mov [bz_ztop], ax
    jmp short .win
    ; step 4's two seldom-taken parts, out of its line: a cell change ...
.wcx:
    inc cx                      ; (wx changed: wy's test, here)
    mov ax, [bz_gy + 1]
    and al, 0f0h
    cmp ax, [bz_wgy]
    je .w2
.wcy:
    or cl, 2
.w2:
    mov [bz_wch], cl
    call bz_sstart              ; a new cell: the START's ground position kept
                                ; for the fallback's undo (gx - gvx: only the
                                ; move has touched it yet)
    call bz_win9i               ; the centre's new cell
    jmp short .w3
.wopen:                         ; ...and a centre of kind VOID
    cmp byte [bz_nbr + BZN_C], BZ_ZOPEN
    jne .w4
    jmp .respawn                ; an OPEN cell (or outside the grid)
    ; ---- 4. the window ----
.win:
    xor cx, cx                  ; CL: bit 0 the cell's wx changed, bit 1 its
    mov ax, [bz_gx + 1]         ; wy (the window is on the START's cell)
    and al, 0f0h
    cmp ax, [bz_wgx]
    jne .wcx
    mov ax, [bz_gy + 1]
    and al, 0f0h
    cmp ax, [bz_wgy]
    jne .wcy
    mov [bz_wch], cl            ; (the same cell: 0, and no jump taken)
.w3:
    test byte [bz_nbr + BZN_C + 2], 0fh
    jz .wopen
.w4:
    mov al, [bz_ps]             ; wave 3 (130.12.6.5 step 4): an OBS cell in the
    and al, 0dh                 ; window, or carried - the PROP path, which sets
    mov [bz_pdoor], al          ; bz_pdoor 1 - 3 here; else 0: wave 2's steps
    jz .walls                   ; 4 - 6, bz_pdoor 0 throughout.  D3: or a SPLIT
    test al, 8                  ; cell (bit 3, SPEC.md 130.24.7.6): the split
    jnz .split                  ; path, the prop path's with its own step 5
    cmp byte [bz_wch], 0        ; the START for the fallback's undo, which
    jne .pst0                   ; wave 2 keeps only on a cell change (a post's
    call bz_sstart              ; push can change it here) ...
.pst0:                          ; (the lift's carry moves z alone, which the
                                ; start does not keep: the undo takes it back)
    call bz_sdoor               ; the centre's cell's prop (bz_wol's cell 4):
    mov ax, [bz_wcen]           ; a windmill's IN, its doorway (step 5,
    dec al                      ; bz_pdoor 2 or 3, else 1); a plain tube's IN,
    js .walls                   ; the capture test (step 4)
    cmp ah, BZ_PK_TUBE
    jne .walls
    mov bl, al
    xor bh, bh
    call bz_tdrain              ; (the TUBE family's DRAIN, 130.25.20.2)
    jnc .walls
    jmp .end
.walls:
    ; ---- 5. walls: the circle, the edge test SYMMETRIC (130.11.8.3), every
    ; zeroing a REFLECTION (130.11.8.4); the prop path adds the windmill's
    ; doorway on the -x and -y edges (130.12.6.2) ----
    mov dh, [bz_gy + 1]         ; DL = u, DH = v: integer gu inside C, BP their
    and dh, 15                  ; copy for the y edges (u is the one before
    mov ax, [bz_gx]             ; the x push, as the model)
    and ah, 15                  ; AX = pu, the in-cell x in 1/256 gu
    mov dl, ah
    mov bp, dx
    cmp ax, BZ_RAD * 256
    jae .xe
    mov si, bz_nbr + BZN_W      ; west, at its point (16, v)
    mov dl, 16
    call bz_blocks
    jnc .y
    cmp byte [bz_pdoor], 2      ; a windmill's DOORWAY along -x (130.12.6.2)
    je .trwd
.wwall:
    mov ax, [bz_gx + 1]
    and al, 0f0h
    add al, BZ_RAD              ; the centre BZ_RAD from the edge, no fraction
    mov [bz_gx + 1], ax
    mov byte [bz_gx], 0
    mov byte [bz_bgr], 0        ; wave 6b: an edge's clamp closes the grace
    mov ax, [bz_gvx]            ; into the wall: reflected
    or ax, ax
    jns .y
    call bz_wrefl
    mov [bz_gvx], ax
    jmp short .y
.trwd:                          ; (the short jump's reach)
    jmp .wdoor
.xe:
    cmp ax, (16 - BZ_RAD) * 256 ; east when pu > 2,560: a true distance under
    jbe .y                      ; 6 gu, as west (P1)
    mov si, bz_nbr + BZN_E      ; east, at (0, v)
    mov dl, 0
    call bz_blocks
    jnc .y
    mov ax, [bz_gx + 1]
    and al, 0f0h
    add al, 16 - BZ_RAD
    mov [bz_gx + 1], ax
    mov byte [bz_gx], 0
    mov byte [bz_bgr], 0        ; (6b, every clamp)
    mov ax, [bz_gvx]
    or ax, ax
    jle .y
    call bz_wrefl
    mov [bz_gvx], ax
.y:
    mov dx, bp
    mov ax, [bz_gy]
    and ah, 15                  ; AX = pv
    cmp ax, BZ_RAD * 256
    jae .ye
    mov si, bz_nbr + BZN_N      ; north, at (u, 16)
    mov dh, 16
    call bz_blocks
    jnc .corner
    cmp byte [bz_pdoor], 3      ; ...along -y
    je .trnd
.nwall:
    mov ax, [bz_gy + 1]
    and al, 0f0h
    add al, BZ_RAD
    mov [bz_gy + 1], ax
    mov byte [bz_gy], 0
    mov byte [bz_bgr], 0
    mov ax, [bz_gvy]
    or ax, ax
    jns .nocorner               ; (pushed: exactly BZ_RAD from the edge, so
    call bz_wrefl               ; no corner)
    mov [bz_gvy], ax
    jmp short .nocorner
.trnd:
    jmp .ndoor
.ye:
    cmp ax, (16 - BZ_RAD) * 256
    jbe .nocorner               ; (inside on y: no corner)
    mov si, bz_nbr + BZN_S      ; south, at (u, 0)
    mov dh, 0
    call bz_blocks
    jnc .corner
    mov ax, [bz_gy + 1]
    and al, 0f0h
    add al, 16 - BZ_RAD
    mov [bz_gy + 1], ax
    mov byte [bz_gy], 0
    mov byte [bz_bgr], 0
    mov ax, [bz_gvy]
    or ax, ax
    jle .nocorner
    call bz_wrefl
    mov [bz_gvy], ax
    jmp short .nocorner
.corner:
    mov ax, [bz_gx]             ; the corner: only within BZ_RAD of both a
    and ah, 15                  ; west or east edge and a north or south one
    sub ax, BZ_RAD * 256        ; (pu, pv outside 1,536 .. 2,560).  pv IS
    cmp ax, (16 - 2 * BZ_RAD) * 256 ; outside here: step 5's y half comes only
    jbe .nocorner               ; from an edge test whose neighbour did not
    call bz_corner              ; block (inside, or pushed to exactly BZ_RAD
                                ; from the edge, it went to .nocorner)
.nocorner:
    cmp byte [bz_pdoor], 0      ; the prop path: the posts, the window and
    je .fb                      ; the cell change again, then the fallback
    call bz_posts               ; each post on bz_wol: the circle (130.12.6.3)
    mov ax, [bz_gx + 1]         ; a push into another cell: the window
    and al, 0f0h                ; refilled before the fallback judges it
    cmp ax, [bz_wgx]
    jne .pmv
    mov ax, [bz_gy + 1]
    and al, 0f0h
    cmp ax, [bz_wgy]
    je .pfb
.pmv:
    call bz_win9i
.pfb:
    xor cl, cl                  ; the fallback's cell change is against the
    mov ax, [bz_gx + 1]         ; START's cell
    xor ax, [bz_sgx + 1]
    and al, 0f0h
    jz .pf1
    inc cx
.pf1:
    mov ax, [bz_gy + 1]
    xor ax, [bz_sgy + 1]
    and al, 0f0h
    jz .pf2
    or cl, 2
.pf2:
    mov [bz_wch], cl
.fb:
    ; the fallback: the centre in a new cell that blocks is not entered.
    ; (Step 5 never moves the centre's cell: the window is still on it.)
    mov cl, [bz_wch]
    or cl, cl
    jz .floor
    mov si, bz_nbr + BZN_C
    mov dl, [bz_gx + 1]
    and dl, 15
    mov dh, [bz_gy + 1]
    and dh, 15
    mov bp, cx
    call bz_blocks
    jnc .floor
    test bp, 1                  ; each velocity whose cell coordinate changed,
    jz .ux                      ; reflected off C
    mov ax, [bz_gvx]
    call bz_wrefl
    mov [bz_gvx], ax
.ux:
    test bp, 2
    jz .uy
    mov ax, [bz_gvy]
    call bz_wrefl
    mov [bz_gvy], ax
.uy:
    mov byte [bz_bgr], 0        ; wave 6b: the undo closes the grace
    mov ax, [bz_sgx]            ; undo the move: x and y back, and z (gvz is
    mov [bz_gx], ax             ; as the move found it)
    mov ax, [bz_sgx + 2]
    mov [bz_gx + 2], ax
    mov ax, [bz_sgy]
    mov [bz_gy], ax
    mov ax, [bz_sgy + 2]
    mov [bz_gy + 2], ax
    cmp byte [bz_air], 0
    je .unz
    mov ax, [bz_gvz]
    cwd
    sub [bz_gz], ax
    sbb [bz_gz + 2], dx
.unz:
    call bz_win9i               ; the window round the start's cell again
    cmp byte [bz_onp], 0        ; the undo takes the lift's CARRY back too: z
    je .floor                   ; to the step's start (the model's sgz; never
    mov ax, [bz_cdd]            ; on wave 2's path, bz_onp 0 there)
    cwd
    sub [bz_gz], ax
    sbb [bz_gz + 2], dx
    ; ---- 6. the floor (130.11.8.2, 130.11.8.5, 130.11.8.6): the prop path
    ; first finds a post cell's top or the slab's (after .floor, then .psolid with
    ; BX = that h4), and sets bz_onp after it (.ponp) ----
.floor:
    cmp byte [bz_pdoor], 0
    je .floorh
    mov al, [bz_air]            ; the prop path: a post cell's top, the slab's -
    mov [bz_fair], al           ; (what it began with, for that)
    mov ax, [bz_nland]
    mov [bz_fnl], ax
    mov byte [bz_fslab], 0
    mov ax, [bz_wcen]           ; (bz_wolf's: the centre's prop and its kind)
    dec al
    js .floorh
    mov bl, al
    xor bh, bh
    call bz_lrecsi
    cmp ah, BZ_PK_BUMPER
    je .pfpost
    cmp ah, BZ_PK_PLATFORM
    jne .floorh
    push bx                     ; the lift's SHAFT: the SLAB's top at n + 1
    call bz_slabon              ; when the ball began at or over it less
    pop ax                      ; BZ_CLIMB (130.12.6.4); else the shaft's
    jnc .floorh                ; NEAR VOID
    inc ax
    mov [bz_fslab], al
    mov si, bz_nbr + BZN_C      ; (C for bz_land's bz_bok)
    jmp .psolid
.pfpost:
    call bz_ptop                ; a post cell: the post's top within 6 gu of
    mov si, bz_nbr + BZN_C      ; it (130.12.6.3); C for bz_land's bz_bok
    jmp .psolid
.nfloor:                        ; (.floorh's, out of its line: not a FLOOR)
    cmp al, BZ_KGOAL
    jae .ngs                    ; (a GOAL, or D3's SPLIT centre)
.nf2:
    mov byte [bz_ghv], 0        ; no floor under it: no shadow
    cmp byte [bz_air], 0
    je .takeoff                 ; grounded over no floor: off it goes
    or al, al
    jnz .fnext                  ; (no other kind is under an airborne ball)
    mov al, [si]                ; VOID: below its kill height, 2 z0 px?
    cbw                         ; (z0 QUARTER units, SPEC.md 130.48.1 -
    shl ax, 1                   ; but OPEN's -128 still kills at -512 px,
    cmp ax, -256                ; 4 z0: the fall it always was)
    jne .kq
    shl ax, 1
.kq:
    cmp [bz_gz + 1], ax
    jge .fnext
    jmp .respawn
.floorh:
    mov si, bz_nbr + BZN_C
    mov al, [si + 2]
    and al, 0fh
    cmp al, BZ_KFLOOR
    jne .nfloor                 ; (a FLOOR, nearly always: no jump taken)
.solid:
    cmp byte [si + 1], 0        ; a FLAT floor (most steps): 8 z0 wherever
    jne .sslope                 ; the centre is, without bz_h4 (z0 quarter
    mov al, [si]                ; units, SPEC.md 130.48)
    cbw
    shl ax, 1
    shl ax, 1
    shl ax, 1
    xchg ax, bx                 ; BX = h4, the floor under the centre
.psolid:
    cmp byte [bz_air], 0
    jne .airsolid
    mov byte [bz_bsp], 0        ; round 3b (130.17.17): on the ground, the
                                ; boost is spent no more
    cmp byte [bz_hopw], 0       ; the Hop from the ground (130.11.8.6): the
    je .follow                  ; window open, not stunned, on a FLOOR or GOAL
    cmp byte [bz_mst], 0
    jne .follow
    mov ax, [bz_gvz]            ; gvz = the floor's rate + HOP, at most
    add ax, [bz_mrec + BZM_HOP] ; BZ_VZMAX
    cmp ax, BZ_VZMAX
    jle .hg
    mov ax, BZ_VZMAX
.hg:
    mov [bz_gvz], ax
    mov byte [bz_hopw], 0
    inc word [bz_nhop]
    jmp short .launch           ; (wave 6's TOKEN: bz_toff sets it, 130.16.4.1)
.follow:
    ; grounded: off when h < z + gvz - BZ_G - BZ_STICK, i.e. when
    ; h4 <= floor((z + gvz - BZ_G - 256 BZ_STICK - 1) / 64)
    mov ax, [bz_gvz]
    cwd
    add ax, [bz_gz]
    adc dx, [bz_gz + 2]
    sub ax, BZ_G + 256 * BZ_STICK + 1
    sbb dx, 0
    BZ_Q64
    cmp bx, ax
    jle .launch
    mov ax, bx                  ; z = h: the ball follows the floor
    call bz_setz
    jmp short .gh
.takeoff:                       ; over no floor: no bz_gh (bz_ghv cleared)
    call bz_toff                ; (round 3: a FALL's token too, bz_toff's)
    jmp short .fnext
.launch:                        ; a Hop from the ground or (round 3) a fall:
    call bz_toff                ; the boost's TOKEN (bz_toff's)
    jmp short .gh
.airsolid:
    ; airborne: LAND when z <= h, i.e. when h4 > floor((z - 1) / 64)
    mov ax, [bz_gz]
    mov dx, [bz_gz + 2]
    sub ax, 1
    sbb dx, 0
    BZ_Q64
    cmp bx, ax
    jle .gh
    call bz_land
.gh:                            ; bz_gh, bz_ghv: the floor under an airborne
    mov al, [bz_air]            ; ball over a FLOOR or GOAL (BX = its h4; not
    mov [bz_ghv], al            ; reached over no floor, which cleared it)
    or al, al
    jz .fnext
    mov [bz_gh], bx
.fnext:
    cmp byte [bz_pdoor], 0      ; the prop path: wave 4's four prop rules
    je .safe                    ; (BX = the floor's h4 when it is solid),
    cmp byte [bz_wcen + 1], BZ_PK_CKPT ; then bz_onp, then bz_ps (130.14.18
    jb .pw3                     ; item 3) - wave 3's kinds and none pay this
    call bz_prule               ; compare and no call (bz_prule's .clr, here)
    jmp short .ponp
.pw3:
    test byte [bz_ps], 1
    jz .ponp
    mov byte [bz_inmo], 0
.ponp:                          ; bz_onp (130.12.6.4): SET grounded on, or
    mov al, [bz_fslab]          ; landed on (a bounce too), the slab ...
    or al, al
    jz .pkeep
    cmp byte [bz_fair], 0
    jne .pland
    cmp byte [bz_air], 0        ; (grounded: it followed the slab's top, no Hop
    je .pset                    ; and no take-off)
    jmp short .pkeep
.pland:
    mov dx, [bz_nland]
    cmp dx, [bz_fnl]
    je .pkeep
.pset:
    mov [bz_onp], al
    jmp short .pps
.pkeep:                         ; ...KEPT airborne over its slab - the centre
    cmp byte [bz_onp], 0        ; in its SHAFT (one lift a window, so the
    je .pps                     ; centre's prop is it) ...
    cmp byte [bz_air], 0
    je .pclr
    cmp byte [bz_wcen + 1], BZ_PK_PLATFORM
    je .pps
.pclr:                          ; ...CLEARED otherwise
    mov byte [bz_onp], 0
.pps:
    call bz_psync               ; bz_ps (every step of the prop path ends here)
    ; ---- 8. SAFE and the goal: not shattering ----
.safe:
    cmp byte [bz_mst], BZ_ST_SHAT
    je .end
    cmp byte [bz_air], 0        ; SAFE: grounded only
    jne .goal
    test byte [bz_nbr + BZN_C + 3], BZ_FSAFE
    jz .goal
%if BZ_TITLE
    cmp byte [bz_rspo], 0       ; (a title demo's respawn cell holds it, 130.23.3)
    jne .goal
%endif
    mov ax, [bz_nwin]
    mov [bz_safe], ax
.goal:
    mov al, [bz_nbr + BZN_C + 2] ; the goal: grounded OR AIRBORNE, a finish
    and al, 0fh                 ; line (130.11.8.2 step 8)
    cmp al, BZ_KGOAL
    jb .end
    ja .sgoal                   ; (D3: a SPLIT centre, its picked record's)
    mov si, bz_nbr + BZN_C
.goalr:
%ifdef BZDEV
    cmp byte [bz_mode], 1       ; play or a replay: the benchmark ignores it
    je .end
%endif
    cmp word [bz_goal], 0       ; (a finish sequence rolling on over a second
    jne .end                    ; goal cell: the first one stands, 130.22.6)
    mov al, [si + 3]            ; wave 8b (130.19.4): the cell's EXIT, its
    mov cl, 4                   ; flags' bits 4 - 7
    shr al, cl
    mov [bz_exit], al
    mov byte [bz_goal], 1
    call bz_fstart              ; (a play's: the FINISH SEQUENCE, 130.22.6)
    ; ---- 9. the step counted, the screen state derived ----
.end:
    call bz_derive
.count:
    test byte [bz_fhk], BZ_FH_STEP ; wave 9 (130.25.6.3): the families' STEP
    jnz .fstep
.count2:
    inc word [bz_nstep]
    jnz .counted
    inc word [bz_nstep + 2]
.counted:
    cmp word [bz_tsec], 0       ; wave 7 (130.18.4): after the goal's test, the
    je .tdone                   ; limit's countdown - BZ_SECSTEPS steps a second;
    dec byte [bz_t55]           ; the last second's last step TIMES OUT unless
    jnz .tdone                  ; the goal was set (a tie: the goal wins)
    mov byte [bz_t55], BZ_SECSTEPS
    dec word [bz_tsec]
    call bz_tdset               ; (the clocks' digits, once a second)
    cmp word [bz_tsec], 0
    jne .tdone
    cmp byte [bz_goal], 0
    jne .tdone
    mov byte [bz_tout], 1
    call bz_fstart              ; (the same sequence, the clock at 0)
.tdone:
    pop es
    pop cx
    ret
.fstep:                         ; (out of line) every family's STEP hook
    call bz_fstp                ; (each at its wake, 130.25.6.11)
    jmp .count2
.poked:                         ; (out of the hot path) a harness's POKE: the
    mov al, [bz_pokd]           ; window round the ball's cell, whatever it was,
    mov word [bz_pokd], 0       ; and the drag's remainders zeroed after it
    push ax                     ; (bbcourse.Physics.poke, 130.16.3.1) - or a
    call bz_win9f               ; family's REFILL REQUEST (bz_fref, 130.25.6.3):
    pop ax                      ; the refill alone
    or al, al
    jz .fref
    mov word [bz_drx], 0
.fref:
    jmp .unpoked
    ; ---- 7. RESPAWN, on the last SAFE cell; on a CKPT course on the last
    ; flag touched (the start before any) with the flag's ball (130.14.4.5) ----
.respawn:
    cmp word [bz_goal], 0       ; a FINISH SEQUENCE (130.22.6): a fall, a kill
    je .rsp                     ; plane or an open cell neither kills nor
    mov byte [bz_air], 1        ; respawns - the ball goes on falling (its
    mov ax, [bz_gvz]            ; gravity, clamped), clipped to the window
    sub ax, BZ_G                ; as it leaves it
    cmp ax, -BZ_VZMAX
    jge .rf
    mov ax, -BZ_VZMAX
.rf:
    mov [bz_gvz], ax
    cwd
    add [bz_gz], ax
    adc [bz_gz + 2], dx
    jmp .end
.rsp:
    mov di, bz_nfall            ; a fall's (a RETURN counts bz_nret instead)
.resp:
    xor ax, ax                  ; wave 2's state zeroed (130.11.8.1): the
    mov [bz_lvl], ax            ; levels, (6b) the grace, the window, the
    mov [bz_lvl + 2], ax        ; ball's state, the squash and bz_ghv; wave
    mov [bz_bgr], ax            ; 4's bz_inmo
    mov [bz_mst], ax
    mov [bz_sqf], ax
    mov [bz_inmo], al
    mov [bz_btok], ax           ; wave 6 (130.16.4.3): the token, the stretch
    mov [bz_drx], ax            ; and both remainders; not bz_nboost
    cmp byte [bz_fhk], 0        ; wave 9 (130.25.6.3): the RESPAWN class cleared,
    je .rnf                     ; the families' lanes marked, RESET 1 - before
    call bz_frst                ; the place, whose refill runs the CELL hook
.rnf:
    test byte [bz_gfl], BZ_GF_CKPT
    jnz .rflag
    call bz_place
.rdone:
    inc word [di]
    mov byte [bz_resp], 1
    call bz_derive
    xor ax, ax                  ; a respawn's screen velocity is 0
    mov [bz_vx], ax
    mov [bz_vy], ax
    jmp .count
    ; ---- wave 3 (SPEC.md 130.12.6.5): the steps a prop changes, out of the
    ; hot path ----
.pst:                           ; step 1 (bz_ps bits 1 - 2): in a TUBE, the
    cmp byte [bz_tube], 0       ; transit instead of the step (130.12.6.1) ...
    jne .transit
    push bx                     ; ...else CARRIED: the slab's displacement,
    call bz_carry               ; step 3's first move, made here - the forces
    pop bx                      ; read nothing of the position (130.12.6.4)
    jmp .forces2
.transit:
    call bz_transit
    jmp .end
    ; ---- wave 4 (SPEC.md 130.14.8.2): a TILT step's ramp, each held arrow's
    ; level capped by its axis's cap - the x cap (the tilt byte's high
    ; nibble) for Left and Right, the y cap for Up and Down: a level above
    ; the cap falls by two a step to it, else it rises by one to it ----
.tilt:
    mov si, bz_lvl
    mov cx, 4
    mov dl, [bz_tby]
    mov dh, dl
    shr dh, 1
    shr dh, 1
    shr dh, 1
    shr dh, 1                   ; DH = the x cap, DL = the y cap
    and dl, 0fh
.tl:
    mov ah, dh                  ; CL 4, 3: Left, Right; 2, 1: Up, Down
    cmp cl, 2
    ja .tc
    mov ah, dl
.tc:
    lodsb
    shr bh, 1
    jnc .trel
    cmp al, ah
    jbe .tup
    sub al, 2                   ; above the cap: max(c, lvl - 2)
    cmp al, ah
    jge .tst
    mov al, ah
    jmp short .tst
.tup:
    jae .tst                    ; at the cap: stays
    inc ax                      ; under it: min(c, lvl + 1)
    jmp short .tst
.trel:
    sub al, 2                   ; released: max(0, lvl - 2), as the keyboard's
    jnc .tst
    xor al, al
.tst:
    mov [si - 1], al
    loop .tl
    jmp .hopw
    ; ---- wave 4 (SPEC.md 130.14.4.5), out of the hot path ----
.kret:                          ; RETURN: one press is one step's bit (a
    and byte [bz_keys], ~BZ_K_RET & 0ffh ; play's bz_input set it for the frame)
    cmp byte [bz_mst], BZ_ST_SHAT ; the ball neither shattering, in a
                                ; tube nor holed - else the key byte runs
    je .kr2                     ; as any other (its bit 6 tested by nothing)
    cmp byte [bz_tube], 0
    jne .kr2
    cmp byte [bz_hid], 0
    jne .kr2
    mov di, bz_nret             ; ...respawns as step 7 does, a RETURN's count
    jmp .resp
.kr2:
    jmp .key2
.rflag:                         ; a CKPT course's respawn: the flag's cell or
    push di                     ; the start's, and its ball
    call bz_rflag
    pop di
    jmp .rdone
.sslope:                        ; step 6's floor on a SLOPE: at the centre's
    mov dl, [bz_gx + 1]         ; point
    and dl, 15
    mov dh, [bz_gy + 1]
    and dh, 15
    call bz_h4
    mov bx, ax
    jmp .psolid
.pdcap:                         ; the doorway open: swallowed
    mov bl, [bz_pdi]
    call bz_capture
    jmp .end
.wdoor:                         ; the ball's circle touches the doorway: low
    mov dx, bp                  ; enough (z <= IN's floor + BZ_CLIMB at its
    call bz_door                ; point, u before the push) - and the gate at
    mov si, bz_nbr + BZN_W      ; the step's n: OPEN swallows it, CLOSED
    cmp al, 1                   ; knocks it back with eG (the ROTOR family's
    jae .wd1                    ; DOOR, 130.25.20.2)
    jmp .wwall
.wd1:
    ja .pdcap
    mov ax, [bz_gx + 1]
    and al, 0f0h
    add al, BZ_RAD
    mov [bz_gx + 1], ax
    mov byte [bz_gx], 0
    mov byte [bz_bgr], 0        ; (6b: a door's clamp too)
    mov ax, [bz_gvx]
    or ax, ax
    jns .wy
    call bz_refl
    mov [bz_gvx], ax
    inc word [bz_nknock]
.wy:
    jmp .y
.ndoor:
    mov dx, bp
    call bz_door
    mov si, bz_nbr + BZN_N
    cmp al, 1
    jae .nd1
    jmp .nwall
.nd1:
    ja .pdcap
    mov ax, [bz_gy + 1]
    and al, 0f0h
    add al, BZ_RAD
    mov [bz_gy + 1], ax
    mov byte [bz_gy], 0
    mov byte [bz_bgr], 0
    mov ax, [bz_gvy]
    or ax, ax
    jns .ny
    call bz_refl
    mov [bz_gvy], ax
    inc word [bz_nknock]
.ny:
    jmp .nocorner               ; (pushed to BZ_RAD from the edge: no corner)
    ; ---- D3 (SPEC.md 130.24.7): THE SPLIT PATH, out of the hot path.  A
    ; window with a split cell runs the prop path's steps 4 and 6 and its
    ; own step 5 (bz_swalls); a course with none never comes here ----
.split:
    mov byte [bz_pdoor], 1      ; (no prop in the window: no windmill, no
    test byte [bz_ps], 5        ; tube, and bz_wcen 0 - bz_wolf's)
    jz .sw
    cmp byte [bz_wch], 0        ; the START for the fallback's undo, as the
    jne .sp0                    ; prop path keeps it: with a prop in the
    call bz_sstart              ; window here; a split centre's lines take
.sp0:                           ; it at their first push (bz_dinner's)
    call bz_sdoor               ; bz_pdoor: 1, or a windmill's doorway
    mov ax, [bz_wcen]           ; the centre a plain tube's IN: its drain
    dec al                      ; (step 4, before the lines inside C)
    js .sw
    cmp ah, BZ_PK_TUBE
    jne .sw
    mov bl, al
    xor bh, bh
    call bz_tdrain              ; (the TUBE family's DRAIN, 130.25.20.2)
    jc .spend
.sw:
    call bz_swalls              ; step 5: the lines inside C, the edges, the
    jc .swcap                   ; corner's rays and the corner (CF: a doorway
    test byte [bz_ps], 5        ; open), then the prop path's posts on - or,
    jz .swpl                    ; with no prop in the window, wave 2's tail
    jmp .nocorner
.swpl:
    mov byte [bz_pdoor], 0      ; (bz_wch against the START again, as .pfb
    cmp byte [bz_srf], 0        ; makes it, when an inner push refilled the
    je .swfb                    ; window round another cell)
    jmp .pfb
.swfb:
    jmp .fb
.swcap:
    jmp .pdcap
.spend:
    jmp .end
.ngs:                           ; step 6: a GOAL, or a SPLIT centre - its
    je .ngg                     ; picked RECORD is C from here (130.24.7.1)
    cmp al, BZ_KFIELD           ; (SPEC.md 130.28.5.1: a FIELD centre's table
    je .nfld                    ; at the point, and the slopes there)
    call bz_srec
    mov [bz_srp], si            ; (and step 8's: the centre does not move)
    mov al, [si + 2]
    and al, 0fh
    cmp al, BZ_KFLOOR
    je .ngg
    cmp al, BZ_KGOAL
    jne .nf2
.ngg:
    jmp .solid
.nfld:
    call bz_fh4                 ; BX = h4, SI = C
    jmp .psolid
.sgoal:                         ; step 8: the split centre's record a GOAL?
    cmp al, BZ_KFIELD           ; (a FIELD centre never is, 130.28.5.2)
    je .sgx
    mov si, [bz_srp]            ; (step 6's pick)
    mov al, [si + 2]
    and al, 0fh
    cmp al, BZ_KGOAL
    jne .sgx
    jmp .goalr
.sgx:
    jmp .end

; -----------------------------------------------------------------------------
; bz_land - step 6's LAND (SPEC.md 130.11.8.5): an airborne ball meets C's
; floor (BX = its h4 under the centre, SI = C).  The impact is judged RELATIVE
; TO THE FLOOR: fr = (sx gvx + sy gvy) >> 2, lvz = max(0, fr - gvz), and the
; rebound r = (e min(lvz, -gvz)) >> 8, e the surface's floor restitution for
; the material (bz_se).  Then, in order: a STUN or a SHATTER (not on a mat);
; the BOOST (130.16.4.1 as wave 6b's 130.17.4.2 has it: the flight ARMED,
; bz_btok 2, not stunned, and bz_bok's rules 3 - 5) leaving at BOOST with the
; stretch and no squash; a Hop at the contact (the window open, not stunned)
; leaving at max(HOP, r if r >= BMIN else 0) + min(fr, 0); a BOUNCE (r >=
; BMIN, Grip not held) at r + min(fr, 0), which OPENS the late grace when the
; token was 1 (unarmed), the ball not stunned and rules 3 - 5 hold
; (130.17.4.5); else it lands.  A landing at lvz >= BZ_SQTHR squashes, but a
; shatter's and a boost's.  Every contact clears bz_btok and closes the grace.
; DS = ours.  Preserves BX and SI.
; Clobbers AX, CX, DX, DI, BP.
; -----------------------------------------------------------------------------
bz_land:
    mov byte [bz_bgr], 0        ; wave 6b: every contact closes the grace
    push bx
    call bz_frate               ; AX = fr, the floor's own rate (C's slopes)
    pop bx
    mov di, ax
    sub ax, [bz_gvz]            ; lvz = max(0, fr - gvz)
    jge .lv
    xor ax, ax
.lv:
    mov [bz_lvz], ax
    mov cx, [bz_gvz]            ; r = (e max(0, min(lvz, -gvz))) >> 8
    neg cx
    cmp ax, cx
    jle .mn
    mov ax, cx
.mn:
    or ax, ax
    jns .mp
    xor ax, ax
.mp:
    mov cl, [bz_se + 3]
    xor ch, ch
    mul cx
    mov al, ah
    mov ah, dl
    mov bp, ax                  ; BP = r
    mov ax, bx                  ; lfall = max(0, ztop - h px), h's px floored
    sar ax, 1
    sar ax, 1
    neg ax
    add ax, [bz_ztop]
    jge .lf
    xor ax, ax
.lf:
    mov [bz_lfall], ax
    mov ax, bx                  ; z = h
    call bz_setz
    inc word [bz_nland]
    mov cx, [bz_mrec + BZM_BMIN] ; CL = BMIN, CH = GRIP (unused); CL = the
    mov al, [bz_mrec + BZM_HARD] ; mat's BZ_BMINMAT and no hard landing on a
    cmp byte [bz_surf], BZ_SURF_BOUNCE ; `bounce` floor (130.11.6.2)
    jne .hard
    mov cl, BZ_BMINMAT
    xor al, al
.hard:
    or al, al
    jz .soft
    mov dx, [bz_lvz]
    cmp dx, [bz_mrec + BZM_HTHR]
    jl .soft
    mov [bz_mst], al            ; 1. STUN or 2. SHATTER: grounded, every
    mov dl, [bz_mrec + BZM_HSTEPS] ; velocity stopped, the state's steps
    mov [bz_mct], dl
    cbw
    xchg ax, di
    shl di, 1
    inc word [bz_nstun - 2 + di] ; bz_nstun or bz_nshat
    xor ax, ax
    mov [bz_gvx], ax
    mov [bz_gvy], ax
    jmp .ground                 ; (near since round 3's held test: the red
.soft:                          ; arms pump and armwin grow the span past 127)
    xor ch, ch                  ; CX = the rebound's floor
    cmp bp, cx
    jae .rok
    xor bp, bp                  ; BP = r if r >= BMIN, else 0
.rok:
    or di, di                   ; DI = min(fr, 0)
    jle .base
    xor di, di
.base:
    cmp byte [bz_mst], 0        ; stunned: a bounce or a landing, nothing else
    jne .bnc
    cmp byte [bz_btok], 1       ; round 3 (130.17.16): Space HELD at the
    jne .armd                   ; contact ARMS the token 1, onto a floor no
    mov al, [bz_kstep]          ; higher than the take-off: z is the
    test al, BZ_K_HOP           ; floor's now (bz_setz above), its px
    jz .armd
    mov ax, [bz_gz + 1]         ; against bz_zoff's
    cmp ax, [bz_zoff]
    jg .armd
    inc byte [bz_btok]
.armd:
    cmp byte [bz_btok], 2       ; 2a. the BOOST (wave 6b, 130.17.4.2): the
    jne .hopc                   ; flight ARMED, and rules 3 - 5 (bz_bok, AX =
    call bz_bok                 ; BOOST); a failing test is the contact Hop
    jc .boost                   ; when the window is open, with no cue
.hopc:
    cmp byte [bz_hopw], 0       ; 3. a HOP AT THE CONTACT: max(HOP, that),
    je .bnc                     ; never a sum (O13)
.chop:
    mov ax, [bz_mrec + BZM_HOP]
    cmp ax, bp
    jae .hp
    mov ax, bp
.hp:
    mov byte [bz_hopw], 0
    inc word [bz_nhop]
    jmp short .leave
.bnc:
    or bp, bp                   ; 4. a BOUNCE: r >= BMIN and Grip not held
    jz .ground
    test byte [bz_kstep], BZ_K_GRIP
    jnz .ground
    inc word [bz_nbnc]
    mov al, [bz_btok]           ; wave 6b (130.17.4.5): an UNARMED first
    dec ax                      ; contact (the token 1), not stunned, may
    or al, [bz_mst]             ; open the late grace (.grace, out of line)
    jz .grace
.bn:
    mov ax, bp
.leave:                         ; still airborne, from this height
    add ax, di
    mov [bz_gvz], ax
    mov ax, [bz_gz + 1]
    mov [bz_ztop], ax
    jmp short .sq
.ground:                        ; 5. lands as wave 1 (and 1., 2.)
    xor ax, ax
    mov [bz_gvz], ax
    mov [bz_air], al
.sq:
    mov byte [bz_btok], 0       ; every contact spends the token (a boost's
    cmp word [bz_lvz], BZ_SQTHR ; own, .boost); the squash, but a shatter's
    jl .out
    cmp byte [bz_mst], BZ_ST_SHAT
    je .out
    mov byte [bz_sqf], BZ_SQSTEPS
.out:
    ret
.boost:                         ; 2a. the BOOST (130.16.4.1, 130.17.4.2;
                                ; AX = BOOST, bz_bok's)
    mov [bz_gvz], ax            ; still airborne at BOOST (a level floor adds
    mov ax, [bz_gz + 1]         ; no rate), ztop = z, the window closed; the
    mov [bz_ztop], ax           ; token spent and the STRETCH's steps set in
    mov byte [bz_hopw], 0       ; one word; and NO squash on this contact
    inc word [bz_nboost]        ; (130.16.4.4: sqf keeps what it held)
    mov word [bz_btok], BZ_STRS << 8
    mov byte [bz_bsp], 1        ; round 3b: spent until the ball is grounded
    ret
.grace:                         ; ...when rules 3 - 5 pass: bz_bgr =
    call bz_bok                 ; BZ_BGRACE and bz_bgd = BOOST less the
    jnc .bn                     ; rebound's gvz, r + min(fr, 0)
    sub ax, bp
    sub ax, di
    mov [bz_bgd], ax
    mov byte [bz_bgr], BZ_BGRACE
    jmp short .bn

; bz_bok - the boost's rules 3 and 4 at a contact (130.16.4.1; bbcourse.Physics's
; _boost_ok and _boost_v), read by the boost and by the late grace's opening
; (130.17.4.5): rule 3, BOOST not 0; rule 4 on the centre's GRID cell, never
; the lift's slab (whose shaft carries OBS): OBS clear (+3), FLOOR or GOAL
; with a `normal` or `ice` surface (+2 AND 0EDh is 01h: kind 1 or 3, surface
; 0 or 1), level (+1, both slopes 0).  Round 3b (130.17.17) took rule 5 out:
; the boost ADDS to the bounce, AX = min(VZMAX, max(BOOST, rr + BADD)), rr
; the rebound (BP, r if r >= BMIN else 0).  -> CF = 1 when both hold, AX the
; boost's gvz.  Clobbers DX.
bz_bok:
    mov ax, [bz_mrec + BZM_BOOST]
    or ax, ax
    jz .no                      ; rule 3 (round 3b: rule 5 went, 130.17.17)
    mov dx, [si + 2]            ; (SI: C, the window's centre - D3: or its
    and dx, (BZ_FL_OBS << 8) | 0edh ; picked record, 130.24.7.1)
    cmp dx, 1
    je .firm
    cmp dx, (BZ_FL_OBS << 8) | 1 ; OBS for a FLAT prop, the centre's owner
    jne .no                     ; (130.16.4.1.1: BZ_BOKT, a bit a kind)
    push bx
    push cx
    mov bl, [bz_wckd]           ; (bz_wcen + 1: its kind, 0 none)
    cmp bl, BZ_BOKTN
    jae .nf
    mov cl, bl
    and cl, 7
    mov ch, 1
    shl ch, cl
    mov cl, 3
    shr bl, cl
    xor bh, bh
    test [bz_bokt + bx], ch
    jnz .f1
.nf:
    pop cx
    pop bx
    jmp short .no
.f1:
    pop cx
    pop bx
.firm:
    mov dx, [bz_mrec + BZM_BADD] ; round 3b: AX = min(VZMAX, max(BOOST, rr
    add dx, bp                  ; + BADD)), the boost ADDED to the bounce
    cmp dx, ax
    jbe .lv
    xchg ax, dx
    cmp ax, BZ_VZMAX
    jbe .lv
    mov ax, BZ_VZMAX
.lv:
    cmp byte [si + 1], 1        ; CF = 1 when both slopes are 0
    ret
.no:
    clc
    ret

;-----------------------------------------------------------------------------
; THE FINISH SEQUENCE (wave 8R, SPEC.md 130.22.6), a PLAY's only (bz_mode 0: a
; replay, a benchmark and a demo end at the finish as the log does).
; bz_fstart - at the step that sets bz_goal or bz_tout: BZ_FIN_STEPS steps to
; run (bz_fcnt is one more: 1 is a sequence run out, which the camera still
; holds through), the flash's first phase (the time shown).  Preserves
; everything.
bz_fstart:
    cmp byte [bz_mode], 0
    jne .r
    mov word [bz_fcnt], (BZ_FIN_STEPS + 1) | (7 << 8)
    push ax                     ; the first phase shows the RUN's time at once
    push bx                     ; (SPEC.md 130.22.6.1), not the seconds left
    call bz_fflash
    pop bx
    pop ax
.r:
    ret

; bz_fstep - one step of the sequence, the frame loop's in place of bz_step
; once bz_goal / bz_tout is set: the keys ZEROED (bz_step's .key2 with BX 0 -
; neither the keys nor the log's recorder are read), the course's CLOCK
; frozen (bz_t55 held off the next second), the flash's clock.  bz_nstep RUNS,
; so the scenery (rotors, lifts, gates) goes on as the ball does; bz_fend
; takes the sequence's steps back off it at the play's end.  A harness's poke
; is honoured as bz_step's is.  Preserves CX and ES as bz_step does.
bz_fstep:
    cmp byte [bz_fcnt], 1
    jbe .r
    cmp byte [bz_fcnt], BZ_FIN_STEPS + 1 ; the finish's first step: the
    jne .nv                     ; VICTORY fanfare over the course's song
    call bzs_victory            ; (130.22.9; its own tests: a goal, an arm,
.nv:                            ; music, the fanfare had)
    call .in
    dec byte [bz_fcnt]
    mov al, [bz_ffl]
    dec al
    test al, 7fh
    jnz .st
    xor al, 87h                 ; the phase over: the other one, 7 steps
    mov [bz_ffl], al
    jmp short bz_fflash
.st:
    mov [bz_ffl], al
.r:
    ret
.in:
    push cx
    push es
    mov es, [bz_cseg]
    cmp byte [bz_pokd], 0       ; (a harness's POKE: bz_step's .poked)
    je .k
    mov byte [bz_pokd], 0
    call bz_win9f
    mov word [bz_drx], 0
.k:
    mov byte [bz_tby], BZ_TILT_KEYS
    mov byte [bz_t55], BZ_SECSTEPS
    xor bx, bx
    jmp bz_step.key2

; bz_fend - a PLAY's end, every way out (bz_t0): the steps a finish sequence
; ran (BZ_FIN_STEPS + 1 - bz_fcnt) taken back off bz_nstep, so the log's, the
; face's and the best's time is the finishing step's; bz_fcnt 0; bz_fin
; from bz_goal (an Esc or F in the sequence finished the play too); and
; bz_bseg the material's ball part (bz_fdis's copies may have stood in).
; Clobbers AX.
bz_fend:
    mov al, [bz_goal]
    mov [bz_fin], al
    push bx                     ; the blits' ball part the material's again
    mov bl, [bz_mat]            ; (the DISSOLVE's copies were their source:
    xor bh, bh                  ; bz_fdis)
    shl bx, 1
    mov ax, [bz_bsegs + bx]
    mov [bz_bseg], ax
    pop bx
    xor ax, ax
    xchg al, [bz_fcnt]
    or al, al
    jz .r
    sub al, BZ_FIN_STEPS + 1
    neg al                      ; AL = the sequence's steps, 0 - BZ_FIN_STEPS
    sub [bz_nstep], ax
    sbb word [bz_nstep + 2], 0
.r:
    ret

; bz_fflash - the clock digits' new state - blank (bit 7 of bz_ffl) or the
; RUN's time, frozen (SPEC.md 130.22.6.1: the whole seconds the play took,
; the limit less the seconds left, where the clocks counted those down; a
; timeout's 0 and EXPLORE's clock as they stand) - and
; EVERY clock lane MARKED (130.19.10 item 6 marks them only on a new second);
; bz_lcsec is made unequal so the walk's clock skip does not hold either.  The
; wheel commits the marked digits as ONE group in a finish (bz_wclk).
; Preserves CX.
bz_fflash:
    test byte [bz_ffl], 80h
    jz .show
    xor ax, ax
    mov [bz_tdig], al
    mov [bz_tdig + 1], ax
    jmp short .mk
.show:
    mov ax, [bz_tsec]           ; the seconds left: as they stand with no limit
    cmp byte [bz_tout], 0       ; (EXPLORE's 0, 130.19.8.3) or on a TIMEOUT
    jne .sh                     ; (0: time's up) ...
    cmp byte [bz_xmode], 0
    jne .sh
    mov bl, [bz_crs]
    xor bh, bh
    shl bx, 1
    mov bx, [bz_clims + bx]     ; ...else the limit (bz_pinit's) less them
    or bx, bx
    jz .sh
    sub bx, ax
    mov ax, bx
.sh:
    call bz_tdsax
.mk:
    mov ax, [bz_tsec]
    not ax
    mov [bz_lcsec], ax
    xor bx, bx
.l:
    cmp bl, [bz_nlane]
    jae .r
    cmp byte [bz_lknd + bx], BZ_PK_CLOCK
    jne .n
    mov byte [bz_latt + bx], 1
.n:
    inc bx
    jmp short .l
.r:
    ret

; bz_fdis - THE DISSOLVE (8R.11, SPEC.md 130.22.6), once a frame after bz_foot
; (the frame's sprite, shadow and footprints chosen): in a finish sequence the
; ball is drawn WHOLE for the step that finished and the sequence's first
; BZ_FDSTEPS - 1 steps, then through 7 ORDERED-DITHER densities (k / 8 of its
; pixels hidden, k = 1 - 7, BZ_FDSTEPS steps each, rolling on all the while),
; and from step 8 BZ_FDSTEPS (40, 0.73 s) to the sequence's end it is not
; drawn at all, nor its shadow: HIDDEN as in a tube (bz_hidn; bz_mkboxes
; restores its last footprint and composes nothing for it after).  A hidden
; pixel is the box's own fill, the course under it (bz_boxc), never a hole.
; The dither is 2 x 4 game pixels, anchored to the WORLD's lines and bytes,
; so one byte a line parity a density (bz_fdtab): a mask byte ORed with it
; (a set bit keeps the box), a frame byte ANDed with its complement (frames
; are pre-ANDed, 130.3), the shadow's mask ORed (AND only, 130.11.10.2) -
; copied into bz_fdb, which the blits then read: bz_smsk, bz_sfd and bz_shm
; point there and bz_bseg is OUR segment until bz_fend puts the material's
; back.  A new density sets bz_spr's bit 7 on every other one, so bz_mkboxes
; never takes the frame for an idle one.  Nothing else changes: the physics,
; the camera (held), the flash and the tune are the sequence's.  A ball
; hidden while it is still whole (a cup's capture) is left as it is; hidden
; once the fade has begun (a tube, a cup the sequence rolls into) it takes
; GONE's path for that frame - no shadow either - because bz_bseg may still
; be OUR segment from the last fading frame while bz_sprite's bz_shm is an
; offset in the ball part.  Clobbers AX, BX, CX, DX, SI, DI, BP.
%if BZ_BAL_ROWS & 1
 %error "bz_fdis swaps a row's dither a row: the ball's rows must be even"
%endif
bz_fdis:
    mov al, [bz_fcnt]
    or al, al
    jz .r                       ; (every frame but a finish sequence's)
    mov ah, BZ_FIN_STEPS + 1
    sub ah, al                  ; AH = the sequence's steps run
    xor cx, cx
.d:
    sub ah, BZ_FDSTEPS
    jc .k
    inc cx
    jmp short .d
.k:
    jcxz .r                     ; CX = the density k: 0 whole
    cmp cl, 8
    jae .gone
    cmp byte [bz_hidn], 0       ; HIDDEN in the fade (a tube, a cup the
    je .dith                    ; sequence rolled into): GONE's path, as
.gone:                          ; bz_bseg may still be our copies' segment
    mov byte [bz_hidn], 1       ; GONE: the ball and its shadow
    mov byte [bz_shc], 0
.r:                             ; wave 9 (SPEC.md 130.25.19): every way out
    mov al, [bz_cue]            ; takes the pickup CUE's look (bzvideo.inc
    or al, [bz_clook]           ; bz_cuef) while a cue shows or the last
    jnz bz_cuef                 ; frame's did - with neither, three tests
    ret
.dith:
    test cl, 1                  ; (a new density is a new sprite to bz_mkboxes)
    jz .p
    or byte [bz_spr], 80h
.p:
    push es
    mov bx, cx
    shl bx, 1
    push word [bz_fdtab - 2 + bx] ; k's bytes: an even line's, an odd line's
    mov bl, [bz_mat]
    xor bh, bh
    shl bx, 1
    mov bp, [bz_bsegs + bx]     ; BP = the material's ball part, the source
    mov [bz_bseg], ds           ; ...and the blits' source: the copies, ours
    push ds
    pop es
    pop dx
    push dx
    mov al, [bz_py]
    call .wd                    ; DX the sprite's row 0's dither, BX row 1's
    mov si, [bz_smsk]
    mov di, bz_fdb
    mov [bz_smsk], di
    mov cx, BZ_BAL_ROWS
    push si
    call bz_fdor                ; the mask: OR
    pop si
    add si, [bz_sfd]
    mov word [bz_sfd], BZ_FDMSK
    not dx                      ; (row 0's again: the rows are even)
    not bx
    mov cx, BZ_BAL_ROWS
    call bz_fdand               ; the frame: AND NOT
    pop dx
    cmp byte [bz_shc], 0
    je .out
    mov al, [bz_spy]
    call .wd
    mov si, [bz_shm]
    mov [bz_shm], di
    mov cx, BZ_BAL_SHDROWS
    call bz_fdor                ; the shadow's mask: OR
.out:
    pop es
    jmp short .r
.wd:                            ; DL an even line's dither byte, DH an odd
    test al, 1                  ; one's, AL a line: DX = AL's (both bytes),
    jz .w0                      ; BX the next line's
    xchg dl, dh
.w0:
    mov bl, dh
    mov bh, dh
    mov dh, dl
    ret

; -----------------------------------------------------------------------------
; bz_cuef - wave 9 (SPEC.md 130.25.9, 130.25.19): the pickup CUE's LOOK for the
; frame, once a frame from bz_fdis's tail while [bz_cue] (a family's STEP
; writes it; display only) or the last frame's look is set.  The look
; (bz_clook): while bit 0 of bz_cue is set, BZ_CL_SP + the sparkles' HOP
; count mod 16: sparkle k holds a place for 8 frames, its epoch e_k =
; (frames + 0, 5, 2) / 8 - the three hop on frames 0, 3 and 6 mod 8, never
; together - so the hops so far are e_0 + e_1 + e_2 = 3 frames / 8, which
; moves at each hop and at no other frame (bar 3 frames' 16-bit wrap: one
; extra recompose in 6 minutes).  On
; a FLASH frame under bit 1 (the last PU_WARN steps: every 4th frame, BLINK4)
; BZ_CL_BL, the ball not drawn.  bz_boxc and bz_blit draw from it.  When
; the look changes, bz_ospr (the sprite bz_mkboxes's idle test compares
; against: last frame's) is made this frame's bz_spr NOT, so that test
; recomposes a RESTING ball on exactly the frames its cue's look changed -
; a hop, the first, and the one the cue ends on included - whatever the
; frames before it were and whatever the dissolve did to bz_spr's bit 7 this
; frame (a ball that moves is recomposed for its move: the sprite's shift is
; not in the look).  And on that change, with the sparkles, each sparkle's
; PLACE (bz_spq: a pointer to its four entries in the card's table, the
; place e_k mod 4 as the steps a b c b) - only at a hop or the sparkles'
; start, not at a flash turning on or off.  (The first build flipped
; a toggle XORed into bz_spr - the dissolve's trick - and a cue that began
; with the toggle left set by the last one changed nothing the idle test
; saw.)  Clobbers AX, CX, DX.
; -----------------------------------------------------------------------------
bz_cuef:
    mov ah, [bz_cue]
    xor dx, dx                  ; DL = the look
    test ah, 2
    jz .sp
    test byte [bz_frames], 3    ; every 4th frame
    jnz .sp
    mov dl, BZ_CL_BL
.sp:
    test ah, 1
    jz .lk
    mov ax, [bz_frames]
    mov cx, ax
    shl ax, 1
    add ax, cx
    mov cl, 3
    shr ax, cl                  ; the HOPS: 3 frames / 8, one a hop
    and al, 0Fh
    or al, BZ_CL_SP
    or dl, al
.lk:
    mov al, [bz_clook]
    cmp dl, al
    je .r
    mov [bz_clook], dl
    mov dh, [bz_spr]            ; a changed look: never an idle frame
    not dh
    mov [bz_ospr], dh
    test dl, BZ_CL_SP
    jz .r
    xor al, dl                  ; the places only at a HOP (or the sparkles'
    test al, BZ_CL_SP | 0Fh     ; start): a flash on or off moves none
    jz .r
    push bx                     ; each sparkle's place, a pointer into the
    mov dx, bz_spr0             ; card's table, off the epochs
    cmp byte [bz_herc], 0       ; (frames + 0, 5, 2) / 8 (a byte's wrap is
    je .pc                      ; 32 epochs: 0 mod 4) - all three: at a hop
    add dx, BZ_SPRC             ; one moves, but picking it costs the bytes
.pc:                            ; it saves (MEASURED: 50 - 90 clk a hop
    mov al, [bz_frames]         ; frame for 41 bytes)
    mov cl, 3
%assign BZ_SPK 0
%rep 3
    mov bl, al
 %if BZ_SPK == 1
    add bl, 5
 %elif BZ_SPK == 2
    add bl, 2
 %endif
    shr bl, cl
    and bx, 3                   ; e_k mod 4, the step...
    mov bl, [bx + bz_sps + 4 * BZ_SPK]  ; ...its place (a b c b)
    add bx, dx
    mov [bz_spq + 2 * BZ_SPK], bx
 %assign BZ_SPK BZ_SPK + 1
%endrep
    pop bx
.r:
    ret

; bz_fdor / bz_fdand - CX rows of the ball part's BZ_BAL_RB bytes from BP:SI to
; ES:DI, each ORed (ANDed) with DX, BX the next row's: the two swapped a row.
; -> SI, DI past them, DX and BX swapped CX times.  Clobbers AX, CX.
%if BZ_BAL_RB != 5
 %error "bz_fdor's rows are two words and a byte (SPEC.md 130.3's 5-byte rows)"
%endif
bz_fdor:
    push ds
    mov ds, bp
.l:
    lodsw
    or ax, dx
    stosw
    lodsw
    or ax, dx
    stosw
    lodsb
    or al, dl
    stosb
    xchg dx, bx
    loop .l
    pop ds
    ret
bz_fdand:
    push ds
    mov ds, bp
.l:
    lodsw
    and ax, dx
    stosw
    lodsw
    and ax, dx
    stosw
    lodsb
    and al, dl
    stosb
    xchg dx, bx
    loop .l
    pop ds
    ret

; the densities k = 1 - 7: the bytes (an even line's, an odd line's) of the
; 2 x 4 ordered dither [0 4 2 6 / 5 1 7 3] - a game pixel hidden where its
; entry is under k (its two bits set; pixel 0 is bits 7 - 6): each density
; one pixel more of the eight, alternating the lines, a checkerboard at 4
bz_fdtab:
    db 0c0h, 000h, 0c0h, 030h, 0cch, 030h, 0cch, 033h
    db 0fch, 033h, 0fch, 0f3h, 0ffh, 0f3h


; bz_tdset - wave 7 (SPEC.md 130.18.5): bz_tdig from bz_tsec, the clocks'
; digit poses - units, tens, hundreds; 0 a blank (a leading zero), 1 + d the
; digit d; the units never blank (bbcourse.clock_pose).  Two DIVs, once a
; second.  Preserves all but the flags.
bz_tdset:
    push ax
    mov ax, [bz_tsec]
%if BZ_PATH_NPAD
    cmp byte [bz_crs], BZ_CRS_PATH ; wave 8b (130.19.5): the pathway's clock
    jne .t                      ; shows the LIVES (no countdown runs there)
    mov al, [bz_lives]
    xor ah, ah
.t:
%endif
    call bz_tdsax
    pop ax
    ret
; bz_tdsax - the same from AX (0 - 999): the finish's run time (bz_fflash)
bz_tdsax:
    push ax
    push cx
    push dx
    mov cl, 10
    div cl                      ; AL = tsec / 10 (at most 99), AH the units
    inc ah
    mov [bz_tdig], ah
    xor dx, dx                  ; DL the tens' pose, DH the hundreds'
    or al, al
    jz .w
    xor ah, ah
    div cl                      ; AL the hundreds, AH the tens
    inc ah
    mov dl, ah
    or al, al
    jz .w
    inc al
    mov dh, al
.w:
    mov [bz_tdig + 1], dx
    pop dx
    pop cx
    pop ax
    ret

; bz_toff - TAKE OFF from the ground (130.10.7.3, and the Hop's, 130.11.8.6):
; airborne, ztop = z, z += gvz, keeping gvz; the boost's TOKEN 1 and the
; take-off's z (rounds 3 and 3b, 130.17.16 - 17: a Hop, a fall, the cup's
; lip-out and a spring under a grounded ball all come here), the boost spent
; no more.  Clobbers AX, DX.
bz_toff:
    mov byte [bz_air], 1
    mov byte [bz_btok], 1
    mov byte [bz_bsp], 0
    mov ax, [bz_gz + 1]
    mov [bz_ztop], ax
    mov [bz_zoff], ax           ; round 3 (130.17.16): the take-off's z
    mov ax, [bz_gvz]
    cwd
    add [bz_gz], ax
    adc [bz_gz + 2], dx
    ret

; =============================================================================
; WAVE 4's PROPS (SPEC.md 130.14.4, 130.14.18 item 3): bbcourse.Physics's
; _cup, _spring, the pad's and the flag's rules, _respawn and _setmat,
; integer-exact.  ES = the course throughout.
; =============================================================================

; bz_prule - the four rules on the PROP path, after step 6's floor, landing or
; bounce and before bz_onp and bz_ps, for the centre's cell's OBS owner
; (bz_wcen: the window is on the centre's cell here) - a SPRING, the CUP, a
; PAD, a FLAG; one cell has one prop, so at most one fires.  On the prop path
; a centre whose owner is not the cup clears bz_inmo.  BX = the floor's h4
; under the centre when its cell is solid (a spring's and the cup's always
; are); bz_fair the air state step 6 began with, bz_fnl bz_nland then.  A
; rule that launches the ball sets bz_ghv and bz_gh as step 6 would have for
; an airborne ball (the model's shadow update comes after the rules).
; Preserves BX.  Clobbers AX, CX, DX, SI, DI.
bz_prule:
    test byte [bz_ps], 1        ; (the model's `if self.wol`)
    jz .out
    mov ax, [bz_wcen]           ; AL = the centre's prop + 1, AH = its kind
    cmp ah, BZ_PK_CKPT          ; (both 0: no owner) none, or wave 3's -
    jb .clr                     ; MILL's whole cost here
    dec ax                      ; AL = its index
    cmp ah, BZ_PK_CUP
    je .cup
    mov byte [bz_inmo], 0
    cmp ah, BZ_PK_SPRING        ; story 9.8 (SPEC.md 130.25.20): a SPRING is the
    jne .nspr                   ; SPRING family's, its CONTACT by its key
    mov ah, BZ_FK_SPRING
    jmp short .fam
.nspr:
    cmp ah, BZ_PK_PAD
    je .pad
    cmp ah, BZ_PK_CKPT
    je .flag
    cmp ah, BZ_FK0              ; wave 9 (130.25.6.3): a FAMILY kind's CONTACT
    jae .fam
.out:
    ret
.clr:
    mov byte [bz_inmo], 0
    ret
.fam:
    push bx                     ; (BX, the floor's h4, is kept)
    mov bl, al                  ; BX = the element, DL its kind, AH the argument
    xor bh, bh                  ; (the kind)
    mov dl, ah
    mov al, BZ_HK_CONT
    call bz_fone
    pop bx
    ret
.flag:                          ; A FLAG (130.14.4.5), grounded or airborne,
    cmp byte [bz_mst], BZ_ST_SHAT ; not shattering: the respawn point and its
    je .out                     ; ball; first touched, its bit and bz_nckpt
    call .rec
    mov cl, [es:si + BZP_CNUM]
    mov al, cl
    inc ax
    mov [bz_ckpt], al
    mov al, [es:si + BZP_CBALL] ; the FLAG's ball, not the one it was
    mov [bz_ckmat], al          ; touched with
    mov al, 1
    shl al, cl
    test [bz_cksn], al
    jnz .out
    or [bz_cksn], al
    inc word [bz_nckpt]
    mov ax, si                  ; (130.19.10: a first touch MARKS its flag's
    sub ax, [bz_poff]           ; lane for the walk: the record's index)
    mov cl, 5
    shr ax, cl
    xchg ax, bx
    mov byte [bz_latt + bx], 1
    xchg ax, bx
    ret
.rec:                           ; SI = record AL's offset in the course
    push bx
    mov bl, al
    xor bh, bh
    call bz_lrecsi
    pop bx
    ret
.pad:                           ; A PAD (130.14.4.4): grounded, not
    cmp byte [bz_air], 0        ; shattering, a material other than the
    jne .out                    ; ball's - the swap, its record and tables
    cmp byte [bz_mst], BZ_ST_SHAT
    je .out
    call .rec
    mov al, [es:si + BZP_DMAT]
    cmp al, [bz_mat]
    je .out
    call bz_setmat
    inc word [bz_npad]
    ret
.cup:                           ; THE CUP (130.14.4.3): in its MOUTH, |u - 8|
    call .rec                   ; and |v - 8| at most the half-width
    mov cl, [es:si + BZP_UHW]
    mov al, [bz_gx + 1]
    call .mouth
    ja .nomo
    mov al, [bz_gy + 1]
    call .mouth
    ja .nomo
    mov al, [bz_fair]           ; began the step grounded, ends it grounded,
    or al, [bz_air]             ; neither stunned nor shattering
    or al, [bz_mst]
    jnz .inmo
    call bz_vmax                ; max(|gvx|, |gvy|) <= capture: HOLES OUT
    cmp ax, [es:si + BZP_UCAP]
    ja .lip
%ifdef BZDEV
    cmp byte [bz_mode], 1       ; ...in a play or a replay (the goal line's
    je .inmo                    ; rule: the benchmark rolls over it)
%endif
    cmp word [bz_goal], 0       ; (in a FINISH SEQUENCE, a goal line's or a
    jne .hole                   ; timeout's: holed, the finish unchanged)
    mov al, [es:si + BZP_UEXIT] ; wave 8b (130.19.4): the cup's EXIT (bit 7
    and al, 0fh                 ; hidden is the pathway's)
    mov [bz_exit], al
    mov byte [bz_goal], 1
    call bz_fstart              ; (a cup's finish: the same sequence)
.hole:
    xor ax, ax
    mov [bz_gvx], ax
    mov [bz_gvy], ax
    mov [bz_gvz], ax
    inc ax
    mov [bz_hid], al
    jmp short .inmo
.lip:                           ; faster, on the step it ENTERS the mouth: it
    cmp byte [bz_inmo], 0       ; LIPS OUT, a pop of BZ_LIPZ the ground Hop's
    jne .inmo                   ; shape, its ground velocity kept
    mov word [bz_gvz], BZ_LIPZ
    call bz_toff
    inc word [bz_nlip]
    call .launched
.inmo:
    mov byte [bz_inmo], 1
    ret
.nomo:
    mov byte [bz_inmo], 0
    ret
.mouth:                         ; CF/ZF: |(AL AND 15) - 8| above CL (JA)
    and al, 15
    sub al, 8
    jns .m1
    neg al
.m1:
    cmp al, cl
    ret
.launched:                      ; the shadow's floor for the now airborne ball
    mov byte [bz_ghv], 1        ; (its cell solid: BX the h4)
    mov [bz_gh], bx
    ret

; bz_vmax - AX = max(|gvx|, |gvy|): a tube's entry speed, the cup's test.
; Clobbers CX, DX.
bz_vmax:
    mov ax, [bz_gvx]
    cwd
    xor ax, dx
    sub ax, dx
    xchg ax, cx
    mov ax, [bz_gvy]
    cwd
    xor ax, dx
    sub ax, dx
    cmp ax, cx
    jae .s
    xchg ax, cx
.s:
    ret

; bz_setmat - the ball becomes material AL (a pad's swap, a respawn's flag
; ball; bbcourse.Physics._setmat): bz_mat, its BZ_MATTAB record copied into
; bz_mrec, the air's force table rebuilt, the ground's and bz_se for the
; window centre's surface (bz_surfset), and the sprite's part bz_bseg =
; bz_bsegs[AL] (the display's, from the next frame).  Preserves BX and ES.
; Clobbers AX, CX, DX, SI, DI.
bz_setmat:
    push bx
    push es
    push ds
    pop es
    mov [bz_mat], al
    mov bl, al
    xor bh, bh
    shl bx, 1
    mov si, [bz_bsegs + bx]
    mov [bz_bseg], si
    mov ah, [bz_spr]            ; a new material is a new picture: never an
    not ah                      ; idle frame (bz_mkboxes compares no material;
    mov [bz_ospr], ah           ; a swap on a still ball drew nothing, 130.14.4.4)
    mov ah, BZ_MATREC
    mul ah
    add ax, bz_mattab
    xchg ax, si
    mov di, bz_mrec
    mov cx, BZ_MATREC / 2
    rep movsw
    mov al, [bz_mrec + BZM_ACC]
    mov di, bz_fta
    mov cl, 4
    call bz_ramp
    mov al, [bz_surf]
    call bz_surfset
    pop es
    pop bx
    ret

; bz_rflag - step 7 on a CKPT course (SPEC.md 130.14.4.5): the ball placed on
; flag bz_ckpt - 1's cell (the start's when bz_ckpt is 0), and given bz_ckmat
; when it has another.  bz_safe is not read.  ES = the course.  Clobbers
; AX, BX, CX, DX, SI, DI.
bz_rflag:
    mov di, [bz_goff]
    mov al, [es:di + BZG_WX]
    mov ah, [es:di + BZG_WY]
    mov dl, [bz_ckpt]
    sub dl, 1
    jc .at
    mov si, [bz_poff]           ; the flag numbered DL: the record of kind
    mov cl, [bz_nprop]          ; CHECKPOINT with that number (the tool wrote
.r:                             ; one, 130.14.4.2)
    cmp byte [es:si + BZP_KIND], BZ_PK_CKPT
    jne .n
    cmp [es:si + BZP_CNUM], dl
    je .f
.n:
    add si, BZ_PROPREC
    dec cl
    jnz .r
    jmp short .at
.f:
    mov ax, [es:si + BZP_WX]
.at:
    call bz_placeat
    mov al, [bz_ckmat]
    cmp al, [bz_mat]
    je .out
    call bz_setmat
.out:
    ret

; =============================================================================
; WAVE 3's PROPS (SPEC.md 130.12.6), bbcourse.Physics's _capture, _transit,
; _circle, _floor and the carry, integer-exact.  ES = the course throughout;
; a record is reached by its index through bz_lrecsi (bzwheel.inc).
; =============================================================================

; bz_psync - bz_ps from its facts: bit 0 bz_wol not empty, bit 1 a tube in
; transit, bit 2 carried by the platform (130.12.3.2); D3: bit 3 a split cell
; in the window (bz_psp, 130.24.7.6).  Preserves all.
bz_psync:
    push ax
    mov al, [bz_psp]
    cmp byte [bz_wol], 0
    je .a
    inc ax
.a:
    cmp byte [bz_tube], 0
    je .b
    or al, 2
.b:
    cmp byte [bz_onp], 0
    je .c
    or al, 4
.c:
    mov [bz_ps], al
    pop ax
    ret

; bz_wolf - bz_wol rebuilt for the window just filled (bz_fill, a course with
; props): its nine cells in bz_wrt's order - NW, W, N, SW, C, NE, S, E, SE, the
; model's Physics.WORDER - and for each OBS cell the record that owns it
; (bz_owner), as a (cell 0 - 8, index) pair; then bz_ps.  Clobbers BX, CX,
; DX, SI, DI and AX.
bz_wolf:
    xor ax, ax
    mov [bz_wcen], ax           ; (and bz_wckd)
    mov [bz_wbmp], al
    mov al, [bz_nbr + 3]        ; no OBS cell in the window (most refills):
%assign bz_i 7                  ; an empty bz_wol, without the nine cells' walk
%rep 8
    or al, [bz_nbr + bz_i]
 %assign bz_i bz_i + 4
%endrep
    test al, BZ_FL_OBS
    jz .none
    mov di, bz_wol + 1
    mov si, bz_wotab
    mov cx, 9
    xor bh, bh                  ; (BX stays under 256 throughout)
.c:
    mov bl, [si + 3]            ; the cell's flags, bz_nbr + 4 cell + 3
    test byte [bz_nbr + bx], BZ_FL_OBS
    jz .n
    mov dx, [bz_nwin]           ; the cell's wx, wy
    add dl, [si + 1]
    add dh, [si + 2]
    call bz_owner               ; AL = the index, AH = its kind
    jc .n
    cmp ah, BZ_PK_CLOCK         ; wave 7 (SPEC.md 130.18.5.3): a CLOCK's cell is
    jne .nk                     ; a POST's - its record carries a post's fields
    mov ah, BZ_PK_BUMPER        ; (no kick, no light), and every post rule reads
.nk:                            ; the kind recorded here
    mov bx, di                  ; the pair's kind beside it
    sub bx, bz_wol + 1
    shr bx, 1
    mov [bz_wkd + bx], ah
    cmp ah, BZ_PK_BUMPER
    jne .nb
    inc byte [bz_wbmp]
.nb:
    mov bl, [si]
    cmp bl, 4
    jne .nc
    inc ax                      ; the centre's
    mov [bz_wcen], ax
    dec ax
.nc:
    mov ah, al
    mov al, bl
    mov [di], ax
    inc di
    inc di
.n:
    add si, 4
    loop .c
    mov ax, di
    sub ax, bz_wol + 1
    shr ax, 1
    mov [bz_wol], al
    jmp bz_psync
.none:
    mov [bz_wol], ah            ; (AH is 0)
    jmp bz_psync
; the window's cells in bz_wrt's order: the cell 0 - 8, dx, dy, and its flags'
; offset in bz_nbr
bz_wotab:
    db 0, -1, -1, 3,  3, -1, 0, 15,  1, 0, -1, 7,  6, -1, 1, 27,  4, 0, 0, 19
    db 2, 1, -1, 11,  7, 0, 1, 31,  5, 1, 0, 23,  8, 1, 1, 35

; bz_owner - the record owning cell DL = wx, DH = wy (130.12.3.2): the first,
; in the records' order, whose anchor is the cell - a tube's or windmill's IN,
; a bumper's post, a lift's shaft.  -> AL = its index, AH = its kind, CF = 0;
; CF = 1 none.
; Preserves all but AX and the flags.
bz_owner:
    push bx                     ; SPEC.md 130.19.10: a BINARY search of
    push cx                     ; bz_okey (the anchors, sorted, the first of
    push si                     ; equal ones first) for its LOWER BOUND - about
    xor bx, bx                  ; 7 compares for 100 props, not 100
    mov cl, [bz_nprop]
    xor ch, ch                  ; [BX, CX) holds it
.bs:
    cmp bx, cx
    jae .lb
    mov si, bx
    add si, cx
    shr si, 1                   ; the middle
    push si
    shl si, 1
    cmp [bz_okey + si], dx
    pop si
    jb .up
    mov cx, si
    jmp short .bs
.up:
    lea bx, [si + 1]
    jmp short .bs
.lb:
    cmp bl, [bz_nprop]
    jae .none
    mov si, bx
    shl si, 1
    cmp [bz_okey + si], dx
    jne .none
    mov al, [bz_oidx + bx]      ; AL the index, AH its kind
    xor ah, ah
    mov si, ax
    mov cl, 5
    shl si, cl
    add si, [bz_poff]
    mov ah, [es:si + BZP_KIND]
    clc
    jmp short .out
.none:
    stc
.out:
    pop si
    pop cx
    pop bx
    ret

; bz_obuild - the owners' index (SPEC.md 130.19.10), at bz_pinit: every
; record's anchor (wx | wy << 8) in bz_okey and its index in bz_oidx, sorted by
; INSERTION, stable - an anchor equal to an earlier one goes after it, so the
; lower bound names the FIRST record of a cell (a clock's units digit), as the
; scan did.  ES = the course.  Preserves all but the flags.
bz_obuild:
    push ax
    push bx
    push dx
    push si
    push di
    mov si, [bz_poff]
    xor bx, bx                  ; BX the record
.i:
    cmp bl, [bz_nprop]
    jae .done
    mov ax, [es:si + BZP_WX]
    mov di, bx                  ; DI the slot it goes to
.j:
    or di, di
    jz .put
    push di
    shl di, 1
    cmp [bz_okey + di - 2], ax
    jbe .putp                   ; (equal stays before: stable)
    mov dx, [bz_okey + di - 2]
    mov [bz_okey + di], dx
    pop di
    mov dl, [bz_oidx + di - 1]
    mov [bz_oidx + di], dl
    dec di
    jmp short .j
.putp:
    pop di
.put:
    push di
    shl di, 1
    mov [bz_okey + di], ax
    pop di
    mov [bz_oidx + di], bl
    add si, BZ_PROPREC
    inc bx
    jmp short .i
.done:
    pop di
    pop si
    pop dx
    pop bx
    pop ax
    ret
%if BZP_WY != BZP_WX + 1 || BZ_PROPREC != 32
 %error "bz_owner compares a record's (wx, wy) as one word and scales by 32"
%endif

%include "fam/bzthunk.inc"      ; story 9.8 (SPEC.md 130.25.20): the TUBE family's thunks
%include "fam/bzdoor.inc"       ; the windmill's doorway: the ROTOR family's

; bz_ppos - the LIFT's (ES:SI, its record) rise above its low top at step AX
; = n, in 1/256 px (130.12.6.4; bbcourse.plat_pos): m = (n + seed) AND
; (P - 1), q = m in the first half and P - 1 - m in the second, pos =
; min(PMAX, max(0, q - W) v).  The last answer is kept (bz_pcn, bz_pcs,
; bz_pcv: a record offset is never 0, so the zeroed state holds none).  -> AX.
; Clobbers DX.
bz_ppos:
    cmp ax, [bz_pcn]            ; the last one asked (bz_carry asks pos(n)
    jne .calc                   ; first, which the last step's floor asked as
    cmp si, [bz_pcs]            ; its pos(n + 1))
    jne .calc
    mov ax, [bz_pcv]
    ret
.calc:
    mov [bz_pcn], ax
    mov [bz_pcs], si
    add ax, [es:si + BZP_SEED]
    mov dh, [es:si + BZP_MASK]
    and al, dh                  ; AL = m
    mov dl, dh
    shr dl, 1                   ; DL = P / 2 - 1
    cmp al, dl
    jbe .q
    sub dh, al
    mov al, dh                  ; q = P - 1 - m
.q:
    xor ah, ah
    sub al, [es:si + BZP_PW]
    jnc .w
    xor al, al
.w:
    mul word [es:si + BZP_PV]
    cmp ax, [es:si + BZP_PMAX]
    jbe .o
    mov ax, [es:si + BZP_PMAX]
.o:
    mov [bz_pcv], ax
    ret

; bz_carry - step 3's CARRY (130.12.6.4), a step that starts with bz_onp: the
; LIFT's rise pos(n + 1) - pos(n) added to z (and kept in bz_cdd for the
; undo).  Clobbers AX, BX, DX, SI.
bz_carry:
    mov bl, [bz_onp]
    dec bx
    xor bh, bh
    call bz_lrecsi
    mov ax, [bz_nstep]
    call bz_ppos                ; pos(n), and then pos(n + 1): what the step's
    push ax                     ; floor and bz_onp ask after it
    mov ax, [bz_nstep]
    inc ax
    call bz_ppos
    pop dx
    sub ax, dx
    mov [bz_cdd], ax
    cwd
    add [bz_gz], ax
    adc [bz_gz + 2], dx
    ret

; bz_slabon - step 6 in the SHAFT of the lift ES:SI: CF = 1 when its slab is
; the floor - the ball began the step at or over its top at n + 1 less
; BZ_CLIMB (zs >= 64 h4 - 256 BZ_CLIMB <=> zq >= h4) - with BX = that h4,
; 4 hP + pos(n + 1) / 64 (pos a multiple of 64: a whole quarter pixel).
; Clobbers AX, BX, CX, DX.
bz_slabon:
    mov ax, [bz_nstep]
    inc ax
    call bz_ppos
    mov cl, 6
    shr ax, cl
    mov bx, [es:si + BZP_PHP]
    shl bx, 1
    shl bx, 1
    add bx, ax
    cmp [bz_zq], bx
    jl .no
    stc
    ret
.no:
    clc
    ret

; bz_octe - the bumpers' OCTANT table's entry for AX = |du|, DX = |dv|
; (130.12.6.3): (a, b) = the larger and the smaller, at a (a + 1) / 2 + b.
; -> CF = 1 when a > BZ_OCTN (no contact); else BX = the entry (|n| along the
; larger, along the smaller, the depth) and CH = 1 when |dv| is the larger.
; Clobbers AX, DX.
bz_octe:
    xor ch, ch
    cmp ax, dx
    jae .s
    xchg ax, dx
    inc ch
.s:
    cmp ax, BZ_OCTN
    ja .no
    mov bl, al
    inc bx
    mul bl
    shr ax, 1
    add ax, dx
    mov bx, ax
    shl ax, 1
    add bx, ax
    add bx, bz_otab
    clc
    ret
.no:
    stc
    ret

; bz_pdist - AX = |gx - post's cx|, DX = |gy - cy| (integer gu; ES:SI the
; bumper's record), BP: bit 0 du < 0, bit 1 dv < 0.  Clobbers nothing else.
bz_pdist:
    xor bp, bp
    mov ax, [bz_gx + 1]
    sub ax, [es:si + BZP_BCX]
    jns .x
    neg ax
    inc bp
.x:
    mov dx, [bz_gy + 1]
    sub dx, [es:si + BZP_BCY]
    jns .y
    neg dx
    or bp, 2
.y:
    ret

; bz_ptop - step 6 on a POST cell (130.12.6.3; ES:SI the bumper): its floor at
; the centre's point, plus the post's height where the octant table's depth
; there is over 96 (within 6 gu of the post's centre).  -> BX = that h4.
; Clobbers AX, CX, DX, BP.
bz_ptop:
    push si
    mov dl, [bz_gx + 1]
    and dl, 15
    mov dh, [bz_gy + 1]
    and dh, 15
    mov si, bz_nbr + BZN_C
    call bz_h4
    pop si
    push ax
    call bz_pdist
    call bz_octe
    pop ax
    jc .out
    cmp byte [bx + 2], 16 * BZ_PRAD
    jbe .out
    mov cl, [es:si + BZP_BH]
    xor ch, ch
    shl cx, 1
    shl cx, 1
    add ax, cx
.out:
    xchg ax, bx
    ret

; bz_posts - step 5's CIRCLES (130.12.6.3): each post on bz_wol in its order,
; bz_circle.  Clobbers AX, BX, CX, DX, SI, DI, BP.
bz_posts:
    cmp byte [bz_wbmp], 0
    je .out
    mov cl, [bz_wol]
    xor ch, ch
    mov di, bz_wol + 1
.p:
    mov bx, di
    sub bx, bz_wol + 1
    shr bx, 1
    cmp byte [bz_wkd + bx], BZ_PK_BUMPER
    jne .n
    push cx
    push di
    mov bl, [di + 1]
    xor bh, bh
    call bz_lrecsi
    mov al, [di]
    call bz_circle
    pop di
    pop cx
.n:
    inc di
    inc di
    loop .p
.out:
    ret

; bz_circle - bumper BX (ES:SI its record, AL its post's window cell): when
; the octant table has a depth at (|du|, |dv|) and the step's START z is
; under the post's top (zs < 256 top <=> zq < 4 top + 16), the centre is pushed
; depth |n| / 4 out along each axis, and with d = (gvx nx + gvy ny) >> 6 the
; outward normal speed, t = max(K, ((BZ_EBUMPER (-d)) >> 8) + KA) when d < 0,
; max(K, d) else, and gv += ((t - d) n) >> 6, each axis clamped; the post's
; kick step = n, bz_nkick + 1.  Clobbers AX, BX, CX, DX, DI, BP.
bz_circle:
    mov cl, al                  ; (the post's window cell)
    call bz_pdist               ; AX = |du|, DX = |dv|, BP their signs: the
    cmp ax, BZ_OCTN             ; table's reach first, the cheap refusal -
    ja .far                     ; before anything is pushed
    cmp dx, BZ_OCTN
    ja .far
    push bx
    mov bl, cl
    xor bh, bh
    push ax
    push dx
    shl bx, 1
    shl bx, 1
    push si
    lea si, [bz_nbr + bx]
    mov dx, 0808h
    call bz_h4                  ; the post cell's floor (flat: as built)
    pop si
    sar ax, 1
    sar ax, 1
    mov cl, [es:si + BZP_BH]
    xor ch, ch
    add ax, cx                  ; its top, px
    shl ax, 1
    shl ax, 1
    add ax, BZ_CLIMB * 4
    cmp [bz_zq], ax
    pop dx
    pop ax
    jge .out
    call bz_octe
    jc .out
    mov cl, [bx]                ; |n| along the larger, along the smaller
    mov dh, [bx + 1]
    or ch, ch
    jz .ns
    xchg cl, dh                 ; (the larger along y)
.ns:
    mov ch, dh                  ; CL = |nx|, CH = |ny|
    mov dl, [bx + 2]            ; the depth (0: no contact)
    or dl, dl
    jz .out
    mov al, dl                  ; the push, along x ...
    mul cl
    shr ax, 1
    shr ax, 1
    test bp, 1
    jnz .xm
    add [bz_gx], ax
    adc word [bz_gx + 2], 0
    jmp short .y
.xm:
    sub [bz_gx], ax
    sbb word [bz_gx + 2], 0
.y:
    mov al, dl                  ; ...and along y
    mul ch
    shr ax, 1
    shr ax, 1
    test bp, 2
    jnz .ym
    add [bz_gy], ax
    adc word [bz_gy + 2], 0
    jmp short .n
.ym:
    sub [bz_gy], ax
    sbb word [bz_gy + 2], 0
.n:
    mov al, cl                  ; DI, CX = nx, ny, the quadrant's signs
    xor ah, ah
    test bp, 1
    jz .nx
    neg ax
.nx:
    xchg ax, di
    mov al, ch
    xor ah, ah
    test bp, 2
    jz .ny
    neg ax
.ny:
    xchg ax, cx
    mov ax, [bz_gvx]            ; d = (gvx nx + gvy ny) >> 6, in 32 bits
    imul di
    mov bx, ax
    mov bp, dx
    mov ax, [bz_gvy]
    imul cx
    add ax, bx
    adc dx, bp
    call bz_sar6
    mov bp, ax                  ; BP = d
    or ax, ax
    jns .t                      ; d >= 0: t = max(K, d)
    neg ax
    mov bx, BZ_EBUMPER          ; d < 0: never under the rail's rebound + KA
    mul bx
    mov al, ah
    mov ah, dl
    add ax, [es:si + BZP_BKA]
.t:
    cmp ax, [es:si + BZP_BK]
    jge .tk
    mov ax, [es:si + BZP_BK]
.tk:
    sub ax, bp                  ; t - d
    mov bp, ax
    imul di                     ; gvx += ((t - d) nx) >> 6, clamped
    call bz_sar6
    add ax, [bz_gvx]
    call bz_gax.clamp
    mov [bz_gvx], ax
    mov ax, bp                  ; gvy the same with ny
    imul cx
    call bz_sar6
    add ax, [bz_gvy]
    call bz_gax.clamp
    mov [bz_gvy], ax
    pop bx
    shl bx, 1
    mov ax, [bz_nstep]
    mov [bz_pkick + bx], ax
    inc word [bz_nkick]
    shr bx, 1                   ; (130.19.10: a kick MARKS its post's lane for
    mov byte [bz_latt + bx], 1  ; the walk, until it is dark again - and makes
    mov byte [bz_lqt], 0        ; the next walk, item 10: the quiet walk reads
                                ; no kick)
    mov byte [bz_bgr], 0        ; wave 6b: a kick closes the grace
    ret
.out:
    pop bx
.far:
    ret

; -----------------------------------------------------------------------------
; bz_frate - the floor's own vertical rate under the ball at its ground
; velocity, (sx gvx + sy gvy) >> 2 with C's slopes (bz_tsx, bz_tsy: 0 off a
; plane floor).  -> AX.  Clobbers BX, CX, DX.
; -----------------------------------------------------------------------------
bz_frate:
    xor cx, cx
    mov ax, [bz_tsx]
    or ax, [bz_tsy]
    jz .out                     ; a flat floor: 0, and no product
    mov ax, [bz_gvx]
    mov bx, [bz_tsx]
    call bz_smul                ; (AX x BX)
    mov cx, ax
    mov ax, [bz_gvy]
    mov bx, [bz_tsy]
    call bz_smul
    add cx, ax
    sar cx, 1
    sar cx, 1
.out:
    xchg ax, cx
    ret

; -----------------------------------------------------------------------------
; bz_gax - one ground axis after its forces (130.11.8.2 step 2): AX through
; the FRACTIONAL DRAG (CL = its shift k, 0: none, ice; SI = the axis's
; remainder byte, bz_drx or bz_dry; SPEC.md 130.16.3.1), then the BRAKE CH
; toward 0 and never past it (0: none), then clamped to +-BZ_VMAXG.  The
; drag, for v not 0 (a ball at rest is not dragged, its remainder kept):
;     t = |v| + rem;  d = t >> k;  rem = t AND bz_dmask;  d = 0: d = 1, rem = 0
; and v moves d toward 0.  rem <= bz_dmask holds at every call (bz_surfset
; cuts it where the mask changes), so the read needs no mask; t < 700.  The
; airborne axis passes CX = 0: the clamp alone.  -> AX.  Preserves SI.
; Clobbers DX (.clamp too, past BZ_VMAXG: wave 9's cap is BZ_VMAXG + bz_vup),
; and BX when CL is not 0.
; -----------------------------------------------------------------------------
bz_gax:
    or cl, cl
    jz .brake
    mov bx, ax
    cwd                         ; DX = v's sign (DH keeps it below)
    xor bx, dx
    sub bx, dx                  ; BX = |v|: 0, no drag
    jz .brake
    add bl, [si]
    adc bh, 0                   ; BX = t = |v| + rem
    mov dl, [bz_dmask]
    and dl, bl                  ; DL = t AND (2^k - 1), the new remainder
    shr bx, cl                  ; BX = d = t >> k
    jnz .d
    inc bx                      ; d = 0: 1, and the remainder 0 (BH is 0)
    mov dl, bh
.d:
    mov [si], dl
    mov dl, dh                  ; DX = the sign again
    xor bx, dx
    sub bx, dx                  ; BX = d with v's sign
    sub ax, bx                  ; v moves d toward 0 (never past it: d <= |v|)
.brake:
    or ch, ch
    jz .clamp
    mov dl, ch
    xor dh, dh
    or ax, ax
    js .bn
    sub ax, dx                  ; v > b: v - b; else 0
    jg .clamp
    xor ax, ax
    jmp short .clamp
.bn:
    add ax, dx                  ; v < -b: v + b; else 0
    jl .clamp
    xor ax, ax
.clamp:
    cmp ax, BZ_VMAXG            ; (inside the clamp, nearly always: no jump
    jg .hi                      ; taken, and not a clock more than before
    cmp ax, -BZ_VMAXG           ; wave 9 - the raise is read only past the
    jl .lo                      ; table's cap)
    ret
.lo:
    neg ax                      ; (|v| < 2^15: no overflow)
    call .hi
    neg ax
    ret
.hi:                            ; wave 9 (SPEC.md 130.25.19): the cap is
    mov dx, BZ_VMAXG            ; BZ_VMAXG + bz_vup, a family's raise (0 but
    add dx, [bz_vup]            ; under PICKUPS' speed)
    cmp ax, dx
    jle .in
    xchg ax, dx
.in:
    ret

; -----------------------------------------------------------------------------
; bz_wrefl - a velocity component AX that met the blocking window cell at SI,
; REFLECTED (SPEC.md 130.11.8.4): t = (e |v|) >> 8, 0 under BZ_WMIN, and
; v = -sign(v) t; e is 230 off a BUMPER (a WALL with a `bounce` surface),
; else the material's stone EW (a floor too high to step onto included).
; bz_refl: the same with BL = e.  -> AX.  Preserve SI, DI, BP; clobber BX,
; CX, DX.
; -----------------------------------------------------------------------------
bz_wrefl:
    mov bl, BZ_EBUMPER
    cmp byte [si + 2], (BZ_SURF_BOUNCE << 4) | BZ_KWALL
    je bz_refl
    mov bl, [bz_mrec + BZM_EW]
bz_refl:
    mov cx, ax                  ; its sign
    or ax, ax
    jns .p
    neg ax
.p:
    cmp ax, BZ_WMIN             ; |v| under WMIN: e |v| >> 8 < |v| (e <= 255),
    jb .z                       ; so 0 exactly, without the MUL - a ball held
    xor bh, bh                  ; against a wall meets it every step
    mul bx                      ; DX:AX = e |v| (under 2^24)
    mov al, ah
    mov ah, dl                  ; >> 8
    cmp ax, BZ_WMIN
    jb .z
    inc word [bz_nwall]         ; SOUND STATE (SPEC.md 130.20.5), never read
    mov [bz_lwv], ax            ; by physics: a reflection that left a speed,
    mov byte [bz_lwb], 0        ; the speed, and whether off a bumper's face
    cmp bl, BZ_EBUMPER
    jne .t
    mov byte [bz_lwb], 1
    jmp short .t
.z:
    xor ax, ax
.t:
    or cx, cx                   ; v < 0: +t;  v >= 0: -t
    js .out
    neg ax
.out:
    ret

; -----------------------------------------------------------------------------
; bz_corner - step 5's corner: the centre within BZ_RAD of both edges at a
; corner (so neither edge neighbour blocked - one that did put the centre
; exactly BZ_RAD from its edge), the corner neighbour blocks, and the corner
; point is nearer than BZ_RAD: the centre pushed out along the normal and the
; velocity's component into the corner REFLECTED (130.10.7.3's table,
; 130.11.8.3's |du|, 130.11.8.4's rule): d = (gvx nx + gvy ny) >> 6; only if
; d < 0, t = (e (-d)) >> 8 (0 under BZ_WMIN), and v -= ((d - t) n) >> 6.
; ES = the course.  Clobbers AX, BX, CX, DX, SI, DI, BP.
; -----------------------------------------------------------------------------
bz_corner:
    xor bp, bp                  ; BP: bit 0 east, bit 1 south
    mov bx, BZN_NW              ; BX = the corner cell's window offset
    mov dx, 1010h               ; DL, DH = the corner cell's point nearest the
    mov ax, [bz_gx]             ; centre: 16 west, 0 east; 16 north, 0 south
    and ah, 15                  ; across: west (|du| = pu >> 8) or east
    cmp ax, BZ_RAD * 256        ; ((4,096 - pu) >> 8)
    jb .cw
    neg ax
    add ax, 4096
    mov bx, BZN_NE
    inc bp
    xor dl, dl
.cw:
    mov cl, ah                  ; CL = |du|
    mov ax, [bz_gy]             ; down: north or south, the same
    and ah, 15
    cmp ax, BZ_RAD * 256
    jb .cn
    neg ax
    add ax, 4096
    add bx, BZN_SW - BZN_NW
    or bp, 2
    xor dh, dh
.cn:                            ; AH = |dv|
    mov ch, ah                  ; the corner cell first: it seldom blocks, and
    mov di, cx                  ; the table's depth is seldom 0 (|du|, |dv|
    lea si, [bz_nbr + bx]       ; wait in DI, which bz_blocks keeps)
    call bz_blocks
    jnc .out
.k:                             ; (D3's entry: SI the blocking record, DI and BP
    mov ax, di                  ; as here - bz_dcorn, bz_dinner's centre)
    mov cl, al                  ; the entry: 3 (6 |du| + |dv|)
    shl al, 1
    add al, cl
    shl al, 1
    add al, ah
    mov cl, al
    shl al, 1
    add al, cl
    xor ah, ah
    mov di, ax
    add di, bz_ctab
    cmp byte [di + 2], 0        ; depth 0: du^2 + dv^2 >= 36, no contact
    je .out
    mov byte [bz_bgr], 0        ; wave 6b: the corner's push closes the grace
    mov bl, BZ_EBUMPER          ; its restitution, kept on the stack
    cmp byte [si + 2], (BZ_SURF_BOUNCE << 4) | BZ_KWALL
    je .e
    mov bl, [bz_mrec + BZM_EW]
.e:
    push bx
    mov al, [di + 2]            ; the push: depth |n| / 4, 1/256 gu, an axis
    mul byte [di]
    shr ax, 1
    shr ax, 1
    test bp, 1
    jnz .mxe
    add [bz_gx], ax             ; west: +x
    adc word [bz_gx + 2], 0
    jmp short .my
.mxe:
    sub [bz_gx], ax             ; east: -x
    sbb word [bz_gx + 2], 0
.my:
    mov al, [di + 2]
    mul byte [di + 1]
    shr ax, 1
    shr ax, 1
    test bp, 2
    jnz .mys
    add [bz_gy], ax             ; north: +y
    adc word [bz_gy + 2], 0
    jmp short .dot
.mys:
    sub [bz_gy], ax             ; south: -y
    sbb word [bz_gy + 2], 0
.dot:
    mov al, [di]                ; CX, SI = nx, ny with the quadrant's signs
    xor ah, ah
    test bp, 1
    jz .nx
    neg ax
.nx:
    mov cx, ax
    mov al, [di + 1]
    xor ah, ah
    test bp, 2
    jz .ny
    neg ax
.ny:
    mov si, ax
    mov ax, [bz_gvx]            ; d = (gvx nx + gvy ny) >> 6, in 32 bits: the
    imul cx                     ; sum can pass a word
    mov bx, ax
    mov bp, dx
    mov ax, [bz_gvy]
    imul si
    add ax, bx
    adc dx, bp
    call bz_sar6
    pop bx                      ; BL = e
    or ax, ax
    jns .out                    ; not moving into the corner
    mov bp, ax                  ; BP = d
    push cx
    call bz_refl                ; AX = t (d < 0: +t)
    pop cx
    sub bp, ax                  ; BP = d - t
    mov ax, bp
    imul cx                     ; gvx -= ((d - t) nx) >> 6
    call bz_sar6
    sub [bz_gvx], ax
    mov ax, bp
    imul si                     ; gvy -= ((d - t) ny) >> 6
    call bz_sar6
    sub [bz_gvy], ax
.out:
    ret

; -----------------------------------------------------------------------------
; bz_blocks - does the window cell at SI block the ball at its point (DL = u,
; DH = v, 0 .. 16)?  A WALL always; a plane floor (FLOOR, GOAL) when its h4
; there is above [bz_zq] - the step's START z plus the climb, grounded or
; airborne (130.11.8.2 step 5); VOID and the reserved kinds never; a
; bumper's post cell never (wave 3, 130.12.6.5: its post is the circle's).
; CF = 1 blocks.  ES = the course.  Clobbers AX, BX, CX.
; -----------------------------------------------------------------------------
bz_blocks:
    mov al, [si + 2]
    and al, 0fh
    cmp al, BZ_KFLOOR           ; (a floor is the likeliest: first, and it
    jne .other                  ; falls through)
.plane:
    cmp byte [si + 1], 0        ; a FLAT floor (most): bz_h4's 8 z0, here
    jne .slope
    mov al, [si]
    cbw
    shl ax, 1
    shl ax, 1
    shl ax, 1
.cmp:
    cmp [bz_zq], ax             ; CF = zq < h4 (signed)
    jl .high
.no:
    clc
    ret
.slope:
    call bz_h4
    jmp short .cmp
.other:
    cmp al, BZ_KWALL
    je .yes
    ja .other2                  ; (VOID: one compare fewer than a GOAL's)
    clc
    ret
.other2:
    cmp al, BZ_KGOAL
    je .plane
    cmp al, BZ_KFIELD           ; SPEC.md 130.28.5.3: a FIELD cell
    je .field
    ; D3 (SPEC.md 130.24.7.3 - 130.24.7.4): a SPLIT window cell is tested by
    ; its RECORD - an edge neighbour's that owns the shared edge, a corner
    ; neighbour's at K (either of two, the first that blocks), the centre's
    ; picked one - and SI is left on the record that decided (its e for the
    ; caller's reflection).  bz_nbp holds each window cell's, bz_wsplit's
    ; from BZ_SPLIT_WIN (the model's OWNER and K_RECS)
    mov bx, si
    sub bx, bz_nbr
    shr bx, 1
    mov ax, [bz_nbp + bx]       ; AL, AH: the record(s) in bz_nbh (FFh none)
    cmp al, 0ffh
    jne .sk
    mov al, [si + 2]            ; the centre: the pick
    and al, 0fh
    call bz_dpick
    shl al, 1
    shl al, 1
    add al, 16 * 4
    mov ah, 0ffh
.sk:
    mov bl, ah
    xor ah, ah
    add ax, bz_nbh
    xchg ax, si                 ; SI = the (first) record
    cmp bl, 0ffh
    je bz_blocks                ; one record: its own test
    push bx
    call bz_blocks              ; (a record's test keeps SI)
    pop bx
    jc .r1                      ; the first blocks: SI on it
    mov al, bl                  ; else the second, at K too
    xor ah, ah
    add ax, bz_nbh
    xchg ax, si
    jmp bz_blocks
.r1:
    ret
.field:                         ; a FIELD record: never from a FIELD centre's
    cmp si, bz_nbr + BZN_C      ; edges and corner (field to field); else by
    je .fpl                     ; its height at the point, as a plane's (and
    mov bl, [bz_nbr + BZN_C + 2] ; the fallback, SI the centre, so)
    and bl, 0fh
    cmp bl, BZ_KFIELD
    je .no
.fpl:
    push di                     ; (bz_blocks keeps DI: bz_corner's)
    call bz_fhp
    pop di
    jmp short .cmp
.lift:                          ; a FIELD centre's LIFT (130.28.5.3): AX = the
    push dx                     ; neighbour's h4; it blocks only above C's own
    push si                     ; at the same point (in C's units) + the climb
    push di
    push ax
    mov bx, si
    sub bx, bz_nbr
    shr bx, 1
    mov ax, [bz_fmap + bx]      ; (16 dx, 16 dy) of this window cell
    add dl, al
    add dh, ah
    mov si, bz_nbr + BZN_C
    call bz_fhp
    add ax, BZ_CLIMB * 4
    pop bx
    pop di
    pop si
    pop dx
    cmp ax, bx
    jl .h2                      ; above it: on to the blocking tests
    clc
    ret
.high:
    cmp si, bz_nbr + BZN_SE     ; an edge or a corner cell of the window (not
    ja .h2                      ; the centre: the fallback is not lifted) ...
    cmp si, bz_nbr + BZN_C
    je .h2
    mov bl, [bz_nbr + BZN_C + 2] ; ... of a FIELD centre: the lift
    and bl, 0fh
    cmp bl, BZ_KFIELD
    je .lift
.h2:
    test byte [si + 3], BZ_FL_OBS ; wave 3: a BUMPER's post cell never blocks
    jnz .obs                    ; (130.12.6.5 step 5; never set with no prop
.yes:                           ; in the window)
    stc
    ret
.obs:
    push dx
    push si
    mov ax, si                  ; the window cell's pair on bz_wol (and its
                                ; prop's kind beside it, bz_wkd)
    sub ax, bz_nbr
    shr ax, 1
    shr ax, 1
    mov cl, [bz_wol]
    xor ch, ch
    mov si, bz_wol + 1
.ol:
    cmp [si], al
    je .of
    inc si
    inc si
    loop .ol
    jmp short .oy
.of:
    sub si, bz_wol + 1
    shr si, 1
    cmp byte [bz_wkd + si], BZ_PK_BUMPER
    pop si
    pop dx
    je .no
    stc
    ret
.oy:
    pop si
    pop dx
    stc
    ret

; =============================================================================
; D3: SPLIT CELLS (SPEC.md 130.24.7) - bbcourse.Physics's prec, _inner and
; _dline and step 5's rays and corner, integer-exact.  Only a window with a
; split cell comes here (bz_ps bit 3: the step's split path, bz_blocks'
; dispatch), or a refill on a GF_SPLIT course (bz_wsplit).  A split cell's
; records are bz_nbh's, 16 x its window index, four bytes each.
; =============================================================================

; bz_dpick - 130.24.7.1's PICK at the centre's in-cell (pu, pv): AL = the split
; kind (4 TB, 5 LR, 6 QUARTERED) -> AL = the record's index - TB 0 when pu <
; pv, else 1; LR 0 when pu + pv < 4,096, else 1; QUARTERED by both, (pu >= pv,
; pu + pv >= 4,096) N (1, 0) 0, E (1, 1) 1, S (0, 1) 2, W (0, 0) 3.
; Clobbers AH, BX, CX.
bz_dpick:
    mov bx, [bz_gx]
    and bh, 0fh
    mov cx, [bz_gy]
    and ch, 0fh
    mov ah, al
    xor al, al
    cmp bx, cx
    jb .t
    inc ax                      ; AL = (pu >= pv)
.t:
    cmp ah, BZ_KTB
    je .r
    add bx, cx
    mov cl, 0
    cmp bx, 4096
    jb .l
    inc cx                      ; CL = (pu + pv >= 4,096)
.l:
    cmp ah, BZ_KLR
    jne .q
    mov al, cl
.r:
    ret
.q:
    or al, al
    jz .w
    mov al, cl                  ; N 0, E 1
    ret
.w:
    mov al, 3                   ; W 3, S 2
    sub al, cl
    ret

; bz_srec - the split centre's RECORD (130.24.7.1): SI = the one the pick
; names, and step 2's slopes from it (bz_tslope) - the next step's, which
; starts where the ball is now.  bz_tslope: SI = a record (or a whole cell):
; bz_tsx, bz_tsy its slopes, 0 unless it is a FLOOR or a GOAL (bz_wtail's).
; Preserve nothing but ES and BP (bz_tslope: SI too; clobbers AX, CX, DX).
bz_srec:
    mov al, [bz_nbr + BZN_C + 2]
    and al, 0fh
    call bz_dpick
    shl al, 1
    shl al, 1
    cbw
    add ax, bz_nbh + 16 * 4
    xchg ax, si
bz_tslope:
    xor ax, ax
    mov dx, ax
    mov cl, [si + 2]
    and cl, 0fh
    cmp cl, BZ_KFLOOR
    je .sl
    cmp cl, BZ_KGOAL
    jne .st
.sl:
    mov al, [si + 1]            ; sy : sx, signed nibbles
    or al, al
    jz .st                      ; (flat, most: both 0 as they are)
    mov ah, al
    mov cl, 4
    shl al, cl
    sar al, cl                  ; AL = sx
    sar ah, cl                  ; AH = sy
    mov dl, ah
    cbw
    xchg ax, dx                 ; DX = sx
    cbw                         ; AX = sy
.st:
    mov [bz_tsx], dx
    mov [bz_tsy], ax
    ret

; bz_wsplit - bz_wtail's for a GF_SPLIT course (130.24.7.6): every split
; cell of bz_nbr has its two or four records copied from section D - its +0 -
; +1, an offset in the course, read through ES (kern_mega: the course's
; selector, no segment arithmetic) - to bz_nbh at 16 x its window index;
; bz_psp is 8 when the window holds one, else 0, and bz_ps's bit 3 with it;
; a split CENTRE's slopes for step 2 (bz_srec).  The part was checked when it
; was built (bbcourse read_part: every offset names its records inside D,
; 130.24.5.2), as every other read of it (bz_crshdr).  ES = the course.
; Clobbers AX, BX, CX, DX, SI, DI.
bz_wsplit:
    xor dl, dl
    mov bx, bz_nbr
    mov di, bz_nbh
.c:
    mov al, [bx + 2]
    and al, 0fh
    cmp al, BZ_KTB
    jb .n
    cmp al, BZ_KFIELD           ; (SPEC.md 130.28: a FIELD cell is none)
    je .n
    mov dl, 8
    push ax                     ; bz_nbp: this cell's record(s) for bz_blocks,
    push bx                     ; BZ_SPLIT_WIN's entry made offsets in bz_nbh
    mov cx, bx
    sub cx, bz_nbr
    shr cx, 1                   ; CX = 2 x the window index
    sub al, BZ_KTB              ; + 9 (the kind - 4)
    mov ah, al
    shl al, 1
    shl al, 1
    shl al, 1
    add al, ah
    mov bx, cx
    shr bx, 1
    add bl, al
    mov al, [bz_swin + bx]      ; first | second << 2 | 16 when two; FFh the centre
    mov ah, 0ffh
    cmp al, ah
    je .p
    mov bl, cl                  ; 16 x the index = 8 CX
    shl bl, 1
    shl bl, 1
    shl bl, 1
    test al, 16
    jz .one
    mov ah, al
    and ah, 0ch
    add ah, bl                  ; the second's offset
.one:
    and al, 3
    shl al, 1
    shl al, 1
    add al, bl
.p:
    mov bx, cx
    mov [bz_nbp + bx], ax
    pop bx
    pop ax
    mov cx, BZ_PAIR / 2         ; a halved cell's words ...
    cmp al, BZ_KQ
    jne .h
    mov cl, BZ_QUAD / 2         ; ... a quartered one's
.h:
    mov si, [bx]
    push di
.w:
    mov ax, [es:si]
    mov [di], ax
    inc si
    inc si
    inc di
    inc di
    loop .w
    pop di
.n:
    add bx, 4
    add di, 16
    cmp bx, bz_nbr + 36
    jb .c
    mov [bz_psp], dl
    mov al, [bz_ps]
    and al, 0f7h
    or al, dl
    mov [bz_ps], al
    mov al, [bz_nbr + BZN_C + 2]
    and al, 0fh
    cmp al, BZ_KTB
    jb .r
    cmp al, BZ_KFIELD
    je .r
    jmp bz_srec
.r:
    ret

; bz_sdoor - the prop path's bz_pdoor for the window's centre (130.12.6.2): 1,
; or 2 / 3 when it is a windmill's IN (its doorway along -x / -y; bz_pdi the
; record).  ES = the course.  Clobbers AX, BX, SI.
bz_sdoor:
    mov byte [bz_pdoor], 1
    mov ax, [bz_wcen]
    dec al
    js .r
    cmp ah, BZ_PK_WINDMILL
    jne .r
    mov bl, al
    xor bh, bh
    call bz_lrecsi
    mov [bz_pdi], al
    mov al, [es:si + BZP_TGVX]  ; 0 -x, 1 -y: bz_pdoor 2 or 3
    add al, 2
    mov [bz_pdoor], al
.r:
    ret

; bz_swalls - step 5 on the split path (SPEC.md 130.24.7.2 - 130.24.7.5,
; the model's order): the lines inside a split centre (bz_dinner), and the
; window refilled round a cell a push carried the centre into (and its
; doorway, bz_sdoor); the four edges as the step's, a split neighbour by its
; record that owns the shared edge (bz_blocks), the windmill's doorway on -x
; and -y; then, a split cell still in the window, the corner's RAYS (bz_dray)
; and the corner through K's records or the other ray's (bz_dcorn) unless the
; facing ray's piece blocked - else today's corner.  -> CF = 1: the doorway
; was OPEN (the caller captures).  ES = the course.  Preserves ES.
bz_swalls:
    mov byte [bz_srf], 0
    mov al, [bz_nbr + BZN_C + 2]
    and al, 0fh
    cmp al, BZ_KTB
    jb .edges
    call bz_dinner
    mov byte [bz_dsn], 0
    mov ax, [bz_gx + 1]
    and al, 0f0h
    cmp ax, [bz_wgx]
    jne .mv
    mov ax, [bz_gy + 1]
    and al, 0f0h
    cmp ax, [bz_wgy]
    je .edges
.mv:
    mov byte [bz_srf], 1        ; (the step's .pfb: the cell against the START)
    call bz_win9i
    call bz_sdoor
.edges:
    mov dh, [bz_gy + 1]         ; BP = (u, v) before any push: both axes'
    and dh, 15                  ; points read it.  The two axes UNROLLED
    mov dl, [bz_gx + 1]         ; (verify-dguest: the table loop was ~180
    and dl, 15                  ; clk an axis); DI = the axis' bz_sedt entry
    mov bp, dx                  ; for a contact's paths
    mov di, bz_sedt
    mov ax, [bz_gx]             ; x: pu, its in-cell 1/256 gu
    and ah, 15
    cmp ax, BZ_RAD * 256
    jae .exh
    mov si, bz_nbr + BZN_W      ; west, at (16, v)
    mov dl, 16
    jmp short .elw
.exh:
    cmp ax, (16 - BZ_RAD) * 256
    jbe .ey
    mov si, bz_nbr + BZN_E      ; east, at (0, v)
    xor dl, dl
    jmp short .ehw
.ey:
    mov di, bz_sedt + BZ_SEDTE
    mov dx, bp
    mov ax, [bz_gy]             ; y: pv
    and ah, 15
    cmp ax, BZ_RAD * 256
    jae .eyh
    mov si, bz_nbr + BZN_N      ; north, at (u, 16)
    mov dh, 16
.elw:                           ; the near side
    call bz_blocks
    jnc .enx
    mov al, [di + 4]            ; the windmill's doorway on this edge?
    cmp al, [bz_pdoor]
    je .edoor
.elo:
    mov bl, BZ_RAD
    call .eclamp
    mov bx, [di + 2]
    mov ax, [bx]
    or ax, ax
    jns .enx
.erf:
    call bz_wrefl               ; (SI: the record that blocked)
.est:
    mov bx, [di + 2]
    mov [bx], ax
.enx:
    cmp di, bz_sedt             ; x done: y
    je .ey
    jmp short .edn
.eyh:
    cmp ax, (16 - BZ_RAD) * 256
    jbe .edn
    mov si, bz_nbr + BZN_S      ; south, at (u, 0)
    xor dh, dh
.ehw:                           ; the far side
    call bz_blocks
    jnc .enx
    mov bl, 16 - BZ_RAD
    call .eclamp
    mov bx, [di + 2]
    mov ax, [bx]
    or ax, ax
    jg .erf
    jmp short .enx
.edn:
    cmp byte [bz_psp], 0        ; the rays, a split cell in the window (the
    je .corn                    ; inner refill can leave none) - and the
    mov ax, [bz_gx]             ; centre near its quadrant's corner K: its
    and ah, 15                  ; distance x sqrt 2 x 256 to K's lines, du +
    cmp ah, 8                   ; dv, under DIAG (a ray's push), or in the
    jb .du                      ; corner zone (its radial).  Neither: no ray
    neg ax                      ; can push, and no corner follows
    add ax, 4096
.du:
    mov cx, [bz_gy]
    and ch, 15
    cmp ch, 8
    jb .dv
    neg cx
    add cx, 4096
.dv:
    mov bx, ax
    add bx, cx
    cmp bx, BZ_DIAG
    jb .ray
    cmp ax, BZ_RAD * 256
    jae .out
    cmp cx, BZ_RAD * 256
    jae .out
.ray:
    call bz_dray
    cmp byte [bz_sfb], 0
    jne .out
.corn:
    mov ax, [bz_gx]             ; the corner zone: pu and pv both outside
    and ah, 15                  ; 1,536 .. 2,560
    sub ax, BZ_RAD * 256
    cmp ax, (16 - 2 * BZ_RAD) * 256
    jbe .out
    mov ax, [bz_gy]
    and ah, 15
    sub ax, BZ_RAD * 256
    cmp ax, (16 - 2 * BZ_RAD) * 256
    jbe .out
    cmp byte [bz_psp], 0
    je .pc
    call bz_dcorn
    jmp short .out
.pc:
    call bz_corner
.out:
    clc
    ret
.edoor:                         ; the doorway: low enough to touch it ...
    mov dx, bp                  ; ... OPEN swallows it (CF = 1 out), CLOSED
    call bz_door                ; knocks it back with eG (the ROTOR family's
    cmp al, 1                   ; DOOR, 130.25.20.2)
    jb .elo
    je .knock
    stc
    ret
.knock:
    push bx
    mov bl, BZ_RAD
    call .eclamp
    pop bx
    mov si, [di + 2]
    mov ax, [si]
    or ax, ax
    jns .enx
    call bz_refl
    inc word [bz_nknock]
    jmp .est
.eclamp:                        ; the axis' centre BL gu into its cell, no
    push si                     ; fraction; the grace closed (6b)
    mov si, [di]
    mov ax, [si + 1]
    and al, 0f0h
    add al, bl
    mov [si + 1], ax
    mov byte [si], 0
    mov byte [bz_bgr], 0
    pop si
    ret
; the two axes' contact paths: the position, the velocity, the doorway's
; bz_pdoor
BZ_SEDTE    equ 5
bz_sedt:
    dw bz_gx, bz_gvx
    db 2
    dw bz_gy, bz_gvy
    db 3

; bz_dinner - 130.24.7.2's lines INSIDE the centre's split cell
; (bbcourse.Physics._inner): the pick's record (bz_dhc); a halved cell's
; diagonal, a quartered one's TB half-line, then its LR one, each pushed off
; (bz_dline, sigma + on the record's side) when the record across it BLOCKS
; at the line's point nearest the centre - TB ((u + v) >> 1, the same), LR
; ((u - v + 16) >> 1, (v - u + 16) >> 1); a push that carries the centre out
; of the cell ends them (R7: nothing more of C's is read); then a quartered
; cell's centre c, the OPPOSITE quarter met radially (bz_corner.k: the corner
; table at |pu - 2,048| >> 8, |pv - 2,048| >> 8) when it blocks at (8, 8) and
; neither partner did.  ES = the course.  Preserves ES.
bz_dinner:
    mov al, [bz_nbr + BZN_C + 2]
    and al, 0fh
    push ax
    call bz_dpick
    mov [bz_dhc], al
    mov byte [bz_dst], 0
    mov byte [bz_dsn], 1        ; (bz_dline: the START at the first push)
    pop cx                      ; CL = the kind
    cmp cl, BZ_KQ
    je .q
    mov ah, al                  ; a halved cell: sigma + in half B ...
    dec ah
    xor al, 1                   ; ... the other half beyond the diagonal
    jmp .line
.q:
    mov bl, al                  ; the TB half-line: sigma + on N and E (pu >=
    mov al, 3                   ; pv), the partner across it 3 - hc
    sub al, bl
    mov ah, bl
    cmp ah, 2
    sbb ah, ah
    not ah
    mov cl, BZ_KTB
    call .line
    jc .ret
    mov bl, [bz_dhc]            ; the LR half-line: sigma + on E and S, the
    mov al, bl                  ; partner hc XOR 1
    xor al, 1
    mov ah, bl
    dec ah
    cmp ah, 2
    sbb ah, ah
    not ah
    mov cl, BZ_KLR
    call .line
    jc .ret
    cmp byte [bz_dst], 0        ; a partner blocked: c is on a straight face
    jne .ret
    xor bp, bp                  ; the centre c: BP bit 0 when pu < 2,048 (the
    mov ax, [bz_gx]             ; push -x), bit 1 when pv < 2,048
    and ah, 0fh
    sub ax, 2048
    jae .cx
    neg ax
    inc bp
.cx:
    cmp ah, 6
    jae .ret
    mov cl, ah                  ; CL = |pu - 2,048| >> 8
    mov ax, [bz_gy]
    and ah, 0fh
    sub ax, 2048
    jae .cy
    neg ax
    or bp, 2
.cy:
    cmp ah, 6
    jae .ret
    mov ch, ah
    mov di, cx
    mov al, [bz_dhc]            ; the opposite quarter, hc XOR 2, at (8, 8)
    xor al, 2
    shl al, 1
    shl al, 1
    cbw
    add ax, bz_nbh + 16 * 4
    xchg ax, si
    mov dx, 0808h
    call bz_blocks
    jnc .ret
    jmp bz_corner.k
.ret:
    ret
.line:                          ; AL = the record across, AH = sigma's mask,
    push ax                     ; CL = the line's kind -> CF = 1: pushed out
    push cx                     ; of the cell
    mov dl, [bz_gx + 1]
    and dl, 15
    mov dh, [bz_gy + 1]
    and dh, 15
    cmp cl, BZ_KTB
    jne .lr
    add dl, dh
    shr dl, 1
    mov dh, dl
    jmp short .pt
.lr:
    mov bl, dl
    sub dl, dh
    add dl, 16
    shr dl, 1
    sub dh, bl
    add dh, 16
    shr dh, 1
.pt:
    shl al, 1
    shl al, 1
    cbw
    add ax, bz_nbh + 16 * 4
    xchg ax, si
    call bz_blocks
    pop cx
    pop ax
    jnc .lx
    mov byte [bz_dst], 1
    mov al, cl
    xor cx, cx                  ; the line's offset: 0 TB, 4,096 LR
    cmp al, BZ_KTB
    je .o
    mov ch, 10h
.o:
    call bz_dset
    jnc .lx
    mov ax, [bz_gx + 1]         ; R7: out of the cell (near a tip)?
    and al, 0f0h
    cmp ax, [bz_wgx]
    jne .lo
    mov ax, [bz_gy + 1]
    and al, 0f0h
    cmp ax, [bz_wgy]
    jne .lo
.lx:
    clc
    ret
.lo:
    stc
    ret

; bz_sstart - BZ_START, the one instance: bz_step's new cell and its prop
; path, the split path (its .split with a prop in the window, bz_dinner's
; first push).  Clobbers AX, DX.
bz_sstart:
    BZ_START
    ret

; bz_dset - bz_dline's line: AL = its kind (TB, LR), AH = sigma's mask (0 for
; +1, FFh for -1), CX = its offset (x 256), SI = the record beyond it.  The
; masks of sx = sigma and sy = -sigma (TB) or sigma (LR) in DI and BP - each
; also the sign word of its product - and DX = sigma x the offset; then
; bz_dline.  Preserves SI, DI, BP; clobbers AX, BX, CX, DX.
bz_dset:
    push di
    push bp
    mov dl, ah
    mov dh, ah
    mov di, dx
    cmp al, BZ_KTB
    jne .lr
    not dx
.lr:
    mov bp, dx
    xor cx, di
    sub cx, di
    mov dx, cx
    call bz_dline
    pop bp
    pop di
    ret
; bz_dline - 130.24.7.2's push and reflection off a DIAGONAL line, the
; cell's own or a corner's ray (bbcourse.Physics._dline, integer-exact): sx,
; sy the signs whose masks DI, BP hold (the line's normal toward the centre),
; DX = sigma x the line's offset.  w = sx pu + sy pv - DX (its distance x
; sqrt 2 x 256); w >= DIAG: nothing, CF = 0.  Else h = (DIAG - w + 1) >> 1,
; gx += sx h, gy += sy h; wv = sx gvx + sy gvy (the velocity into it, x
; sqrt 2) and when wv < 0, t = (e |wv|) >> 8, 0 under BZ_DWMIN (e by the
; record at SI: bz_wrefl's, 230 a bumper half, else the material's EW), k =
; (t + |wv|) >> 1, gvx += sx k, gvy += sy k; bz_bgr = 0; CF = 1.  No clamp:
; every e <= 256 keeps each new component between the old two (130.24.7.2).
; Preserves SI, DI, BP; clobbers AX, BX, CX, DX.
%if BZ_DWMIN != BZ_WMIN
 %error "bz_dline reflects through bz_wrefl, whose dead band is BZ_WMIN: give bz_refl a second entry taking BZ_DWMIN (SPEC.md 130.24.7.2)"
%endif
bz_dline:
    mov ax, [bz_gx]
    and ah, 0fh
    xor ax, di
    sub ax, di                  ; sx pu
    mov cx, [bz_gy]
    and ch, 0fh
    xor cx, bp
    sub cx, bp                  ; sy pv
    add ax, cx
    sub ax, dx                  ; w
    cmp ax, BZ_DIAG
    jl .hit
    clc
    ret
.hit:
    cmp byte [bz_dsn], 0        ; bz_dinner's first push: the step's START
    je .h0                      ; now, gx and gvx as step 4 left them - the
    push ax                     ; value .split takes with a prop in the
    call bz_sstart              ; window.  Only such a push can carry the
    pop ax                      ; centre out of C (the centre's radial ends
    mov byte [bz_dsn], 0        ; 6 gu from c), so a step without one needs
.h0:                            ; none
    neg ax
    add ax, BZ_DIAG + 1
    shr ax, 1                   ; h >= 1
    mov cx, ax
    xor ax, di
    sub ax, di                  ; sx h: its high word the mask
    add [bz_gx], ax
    adc [bz_gx + 2], di
    mov ax, cx
    xor ax, bp
    sub ax, bp
    add [bz_gy], ax
    adc [bz_gy + 2], bp
    mov ax, [bz_gvx]
    xor ax, di
    sub ax, di
    mov cx, [bz_gvy]
    xor cx, bp
    sub cx, bp
    add ax, cx                  ; wv
    jns .nv
    push ax
    call bz_wrefl               ; AX = t (wv < 0: +t)
    pop cx
    sub ax, cx                  ; t + |wv|
    shr ax, 1                   ; k
    mov cx, ax
    xor ax, di
    sub ax, di
    add [bz_gvx], ax
    mov ax, cx
    xor ax, bp
    sub ax, bp
    add [bz_gvy], ax
.nv:
    mov byte [bz_bgr], 0        ; (6b: a wall closes the grace)
    stc
    ret

; bz_dray - 130.24.7.4's RAYS, after the edges: q the centre's quadrant
; (bz_sq), RAYS[q] (BZ_SPLIT_RAYS) its corner K's line; the ray its foot of
; perpendicular falls on FACES the centre.  When that ray's neighbour is split
; along the line (or quartered) and its beyond piece blocks at K, bz_sfb = 1
; (no radial corner: K is on a straight wall) and the circle is pushed off
; the line (bz_dline); the other ray's beyond piece blocking at K is bz_sor
; (else 0), a wall's END at K for the corner.  ES = the course.  Clobbers all
; but ES.
bz_dray:
    xor ax, ax
    mov [bz_sor], ax
    mov [bz_sfb], al
    mov bx, [bz_gx]
    and bh, 0fh                 ; pu
    mov cx, [bz_gy]
    and ch, 0fh                 ; pv
    cmp bh, 8
    jb .q1
    inc ax
.q1:
    cmp ch, 8
    jb .q2
    or al, 2
.q2:
    mov [bz_sq], al
    mov di, ax
    shl di, 1
    shl di, 1
    shl di, 1
    shl di, 1
    add di, bz_srays            ; DI = RAYS[q]
    cmp byte [di + 4], 0        ; the facing test: CF = 0 when it holds
    jne .t1
    cmp bx, cx                  ; pu >= pv
    jmp short .t
.t1:
    add bx, cx
    cmp bx, 4096                ; pu + pv >= 4,096
.t:
    lea bp, [di + 8]            ; (BP: the facing ray)
    jnc .f
    add bp, 4
.f:
    mov si, bp
    call .ray
    jnc .oth
    mov byte [bz_sfb], 1
    mov al, [di]                ; the line: kind, sigma, offset
    mov ah, [di + 1]
    mov cx, [di + 2]
    call bz_dset
.oth:
    mov si, di                  ; the other ray: (DI + 8) + (DI + 12) - BP
    shl si, 1
    add si, 20
    sub si, bp
    call .ray
    jnc .r
    mov [bz_sor], si
.r:
    ret
.ray:                           ; SI = a ray (its cell's offset in bz_nbr, its
    mov bl, [si]                ; beyond quarter, K's u and v) -> CF = 1 when
    xor bh, bh                  ; the piece beyond the line blocks at K, SI
    mov dx, [si + 2]            ; on it.  Preserves DI, BP
    mov al, [bz_nbr + bx + 2]
    and al, 0fh
    mov ah, [di + 5]            ; split along this line: its beyond half
    cmp al, [di]
    je .rr
    mov ah, [si + 1]            ; quartered: its beyond quarter
    cmp al, BZ_KQ
    je .rr
    clc
    ret
.rr:
    mov al, ah
    shl al, 1
    shl al, 1
    xor ah, ah
    shl bx, 1
    shl bx, 1
    add bx, ax
    lea si, [bz_nbh + bx]
    jmp bz_blocks

; bz_dcorn - the corner with a split cell in the window (130.24.7.4's
; "otherwise"): today's (bz_corner), K BLOCKED when the corner neighbour's
; record at K blocks - either of two where K ends its diagonal, bz_blocks'
; dispatch - or else when the other ray's beyond piece does (bz_sor).  The
; centre in the corner zone, bz_sq its quadrant (bz_dray's).  ES = the
; course.  Clobbers all but ES.
bz_dcorn:
    mov bl, [bz_sq]
    xor bh, bh
    mov bp, bx                  ; BP: bit 0 east, bit 1 south (bz_corner's)
    mov ax, [bz_gx]
    and ah, 15
    test bl, 1
    jz .w
    neg ax
    add ax, 4096
.w:
    mov cl, ah                  ; |du|
    mov ax, [bz_gy]
    and ah, 15
    test bl, 2
    jz .n
    neg ax
    add ax, 4096
.n:
    mov ch, ah                  ; |dv|
    mov di, cx
    mov dx, 1010h               ; K in the corner cell: 16 west / north,
    test bl, 1                  ; 0 east / south
    jz .k1
    xor dl, dl
.k1:
    test bl, 2
    jz .k2
    xor dh, dh
.k2:
    mov cl, 4
    shl bx, cl
    mov bl, [bz_srays + bx + 6] ; the corner cell's offset
    xor bh, bh
    lea si, [bz_nbr + bx]
    call bz_blocks
    jc .hit
    mov si, [bz_sor]
    or si, si
    jz .out
.hit:
    jmp bz_corner.k
.out:
    ret

; -----------------------------------------------------------------------------
; bz_h4 - the floor of the plane cell at SI (in bz_nbr) at its point (DL = u,
; DH = v, each 0 .. 16) in QUARTER px: h4 = 8 z0 + sx u + sy v (130.10.4.3;
; z0 in QUARTER units since SPEC.md 130.48).
; The products are bz_prod's, T[n << 4 | u] = n u for n 0 - 7; a negative n
; is -((~n) u + u), T at (~n) << 4 | u (the slope nibble XOR F0h): every
; product -120 .. 105, a byte; the far edge (16) is 16 n, the slope nibble
; moved to the high nibble.  -> AX.  Clobbers BX, CX.
; -----------------------------------------------------------------------------
bz_h4:
    mov ch, [si + 1]            ; sy : sx
    or ch, ch
    jz .flat                    ; no slope: 8 z0 wherever
    mov bx, bz_prod
    mov al, ch
    mov cl, 4
    shl al, cl                  ; 16 sx (signed)
    cmp dl, 16
    je .ue
    or al, dl
    jns .up
    xor al, 0f0h                ; sx < 0: (~sx) u ...
    xlat
    add al, dl                  ; ...+ u, negated: sx u
    neg al
    jmp short .ue
.up:
    xlat                        ; sx u
.ue:
    cbw
    xchg ax, cx                 ; CX = sx u;  AH = the slopes
    mov al, ah
    and al, 0f0h                ; 16 sy (signed)
    cmp dh, 16
    je .ve
    or al, dh
    jns .vp
    xor al, 0f0h                ; (as sx's)
    xlat
    add al, dh
    neg al
    jmp short .ve
.vp:
    xlat                        ; sy v
.ve:
    cbw
    add cx, ax
    mov al, [si]
    cbw
    shl ax, 1
    shl ax, 1
    shl ax, 1                   ; 8 z0
    add ax, cx
    ret
.flat:
    mov al, [si]
    cbw
    shl ax, 1
    shl ax, 1
    shl ax, 1
    ret

; AX = h4 -> bz_gz = 64 h4 (24.8 px: the fraction (h4 & 3) << 6, the whole px
; h4 >> 2, its sign).  Clobbers AX, CX, DX.
bz_setz:
    mov dx, ax
    sar dx, 1
    sar dx, 1
    ror al, 1                   ; (h4 & 3) << 6
    ror al, 1
    and al, 0c0h
    mov [bz_gz], al
    mov [bz_gz + 1], dx
    mov al, dh
    cbw
    mov [bz_gz + 3], ah
    ret

; DX:AX (signed) -> AX = DX:AX >> 6, arithmetic, when that fits a word.
; Preserves all else.
bz_sar6:
    push cx
    push dx
    mov cl, 6
    shr ax, cl
    mov cl, 10
    shl dx, cl
    or ax, dx
    pop dx
    pop cx
    ret

; AX x BX (BX a slope, -8 .. 8) -> AX, by shifts and adds (no IMUL).
; Clobbers BX, DX.
bz_smul:
    xor dx, dx
    or bx, bx
    jns .p
    neg bx
    neg ax
.p:
    shr bx, 1
    jnc .n
    add dx, ax
.n:
    shl ax, 1
    or bx, bx
    jnz .p
    mov ax, dx
    ret

; -----------------------------------------------------------------------------
; bz_win9i - bz_win9f for the step's own refills (its cell change, a post's
; push, the fallback's undo): the centre moved AT MOST ONE CELL each way from
; the window's (bz_nwin), so the six (or four) cells both windows hold are
; MOVED inside bz_nbr and only the three (or five) new ones are read from the
; grid - a move in wx first (a column), then one in wy (a row).  A window
; entry is its own grid cell's four bytes and nothing else (or OPEN outside
; the grid: the same two unsigned tests as bz_fill's, on the cell's own row
; wx + wy - SMIN and its k (wx - wy - AMIN) >> 1), the grid is never written,
; and bz_nbr always holds bz_nwin's window (bz_fill and this are its only
; writers), so the result is bz_fill's, byte for byte; then bz_fill's own
; tail (the slopes, the surface, bz_wol).  Any other move - a centre further
; off, or a byte wx or wy that wrapped - is bz_fill itself.  bz_fnr, bz_fkw
; and bz_frt are the course's, as its last bz_fill left them (bz_pinit's at
; the least); bz_fr, bz_fka and bz_fdp, bz_fill's scratch, are not written.
; ES = the course.  -> AX = bz_nwin.  Preserves ES and nothing else (bz_step's
; three refills keep no register over it).
; -----------------------------------------------------------------------------
bz_win9i:
    mov cl, 4
    mov si, [bz_gx + 1]
    and si, 0ff0h               ; SI = 16 wx, DI = 16 wy (bz_wgx, bz_wgy: wx
    mov di, [bz_gy + 1]         ; and wy are the low BYTES of gu >> 4)
    and di, 0ff0h
    mov ax, di
    shr ax, cl
    mov ah, al
    mov dx, si
    shr dx, cl
    mov al, dl                  ; AL = wx, AH = wy
    mov bx, [bz_nwin]
    mov dx, ax
    sub dl, bl                  ; the move in wx: 0; 1 with no borrow; -1 with
    jz .ty                      ; one - anything else is not a neighbour (a
    sbb cl, cl                  ; byte that wrapped included)
    or cl, 1
    cmp dl, cl
    jne .full
.ty:
    sub dh, bh                  ; ...and in wy
    jz .go
    sbb cl, cl
    or cl, 1
    cmp dh, cl
    jne .full
.go:
    mov [bz_nwin], ax
    mov [bz_wgx], si
    mov [bz_wgy], di
    mov bp, dx                  ; BP = the moves: wx's low, wy's high
    mov cl, bh
    xor ch, ch                  ; CX = the OLD wy: the column is read round
    xor ah, ah                  ; (the new wx, the old wy)
    mov dx, ax
    mov si, [bz_goff]
    add ax, cx
    sub ax, [es:si + BZG_SMIN]  ; AX = R, that centre's grid row ...
    sub dx, cx
    sub dx, [es:si + BZG_AMIN]  ; ...DX = A: its k is A >> 1
    mov bx, bp
    or bl, bl
    jz .ymv
    js .west
    mov si, bz_nbr + 4          ; EAST: cells 1 - 8 down one, then SE, E, NE
    mov cx, 16                  ; read - (R + 2, A), (R + 1, A + 1), (R, A + 2)
    call .shf
    inc ax
    inc ax
    mov di, bz_nbr + BZN_SE
    call .col
    dec dx
    dec dx
    jmp short .ymv
.west:
    mov si, bz_nbr + 30         ; WEST: cells 0 - 7 up one, then SW, W, NW -
    mov cx, 16                  ; (R, A - 2), (R - 1, A - 1), (R - 2, A)
    call .shb
    dec dx
    dec dx
    mov di, bz_nbr + BZN_SW
    call .col
    inc ax
    inc ax
.ymv:
    mov bx, bp
    or bh, bh
    jz .done
    js .north
    mov si, bz_nbr + 12         ; SOUTH (R + 1, A - 1 the centre's): the rows
    mov cx, 12                  ; up one, then SW, S, SE - from (R + 1, A - 3),
    call .shf                   ; the row and A up one a cell
    inc ax
    sub dx, 3
    mov di, bz_nbr + BZN_SW
    jmp short .rowc
.north:
    mov si, bz_nbr + 22         ; NORTH (R - 1, A + 1): the rows down one,
    mov cx, 12                  ; then NW, N, NE - from (R - 3, A + 1)
    call .shb
    sub ax, 3
    inc dx
    mov di, bz_nbr + BZN_NW
.rowc:
    call .cell
    inc ax
    inc dx
    add di, 4
    call .cell
    inc ax
    inc dx
    add di, 4
    call .cell
.done:
    jmp bz_wtail
.full:
    jmp bz_fill
.col:                           ; three cells UP a column: the row down one,
    call .cell                  ; A up one
    dec ax
    inc dx
    sub di, 12
    call .cell
    dec ax
    inc dx
    sub di, 12
.cell:                          ; [DI] = the grid's cell on row AX with A = DX,
    cmp ax, [bz_fnr]            ; OPEN outside it (a negative row or k is
    jae .open                   ; huge).  Preserves AX, DX, DI, BP.
    mov si, dx
    sar si, 1
    cmp si, [bz_fkw]
    jae .open
    mov bx, ax
    shl bx, 1
    add bx, [bz_frt]
    mov bx, [es:bx]             ; ROWTAB[r]: the row's first cell
    shl si, 1
    shl si, 1
    mov cx, [es:bx + si]
    mov [di], cx
    mov cx, [es:bx + si + 2]
    mov [di + 2], cx
    ret
.open:
    mov word [di], BZ_ZOPEN     ; z0 -128, flat, VOID, no flags
    mov word [di + 2], 0
    ret
.shf:                           ; CX words from SI DOWN to bz_nbr.  Preserve
    mov di, bz_nbr              ; AX, DX, BP.
    push es
    push ds
    pop es
    rep movsw
    pop es
    ret
.shb:                           ; CX words UP, the last from SI to bz_nbr + 34:
    mov di, bz_nbr + 34         ; backwards, the direction flag set with the
    push es                     ; interrupts off (no ISR meets it), and POPF
    push ds                     ; puts both back
    pop es
    pushf
    cli
    std
    rep movsw
    popf
    pop es
    ret

; -----------------------------------------------------------------------------
; bz_win9f - the window round the ball's cell (wx, wy = the integer gu >> 4),
; refilled.  bz_fill: the window round AL = wx, AH = wy.  Either sets bz_nwin,
; bz_wgx, bz_wgy (16 wx, 16 wy: what step 4's cell test compares) and bz_tsx, bz_tsy (the
; centre's slopes, sign-extended; 0 unless it is a plane floor, so step 2 reads
; them as they are).  ES = the course.  Preserve all but AX and the flags.
; -----------------------------------------------------------------------------
bz_win9f:
    push cx
    mov ax, [bz_gx + 1]
    mov cx, [bz_gy + 1]
    shr ax, 1
    shr ax, 1
    shr ax, 1
    shr ax, 1
    shr cx, 1
    shr cx, 1
    shr cx, 1
    shr cx, 1
    mov ah, cl                  ; (both < 256)
    pop cx
bz_fill:
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    mov [bz_nwin], ax
    mov bl, ah
    xor bh, bh
    xor ah, ah                  ; AX = wx, BX = wy
    mov cl, 4
    mov dx, ax
    shl dx, cl
    mov [bz_wgx], dx
    mov dx, bx
    shl dx, cl
    mov [bz_wgy], dx
    ; The nine cells are FIVE grid rows (130.10.4.3): s - 2 .. s + 2, each a
    ; run of 1, 2, 3, 2, 1 cells consecutive in k - so one ROWTAB read a row
    ; (bz_wrt is the rows: the first cell's k against the centre's, the run,
    ; the window cells).  A row or a k outside the grid is OPEN.
    mov di, [bz_goff]
    mov cx, [es:di + BZG_NROWS]
    mov [bz_fnr], cx
    mov cx, [es:di + BZG_KW]
    mov [bz_fkw], cx
    mov cx, [es:di + BZG_ROWTAB]
    mov [bz_frt], cx
    mov dx, ax
    add dx, bx
    sub dx, [es:di + BZG_SMIN]
    dec dx
    dec dx                      ; row s - 2's r (a negative r is huge)
    mov [bz_fr], dx
    sub ax, bx
    sub ax, [es:di + BZG_AMIN]  ; a - AMIN: a's parity, AMIN even
    mov cx, ax
    and cx, 1
    dec cx                      ; rows s +- 1 start at k - 1 for an even a, at
    mov [bz_fdp], cx            ; k for an odd one
    sar ax, 1
    mov [bz_fka], ax            ; the centre's k
    mov si, bz_wrt
    mov cx, 5
.row:
    push cx
    lodsw                       ; the first cell's k: 0, -1 or BZ_WRP (row s +- 1)
    cmp ax, BZ_WRP
    jne .dk
    mov ax, [bz_fdp]
.dk:
    add ax, [bz_fka]
    mov cx, ax
    lodsw
    xchg ax, cx                 ; CX = the run, AX = its first k
    mov bx, [bz_fr]
    cmp bx, [bz_fnr]
    jb .rowin
    mov ax, 8000h               ; a row outside the grid: every k "huge"
    jmp short .cell
.rowin:
    shl bx, 1
    add bx, [bz_frt]
    mov bx, [es:bx]             ; ROWTAB[r]: the row's first cell...
    mov dx, ax
    shl dx, 1
    shl dx, 1
    add bx, dx                  ; ...BX = the run's first
.cell:
    mov di, [si]                ; the window cell
    inc si
    inc si
    cmp ax, [bz_fkw]
    jae .open                   ; (a negative k is huge)
    mov dx, [es:bx]
    mov [di], dx
    mov dx, [es:bx + 2]
    mov [di + 2], dx
    jmp short .next
.open:
    mov word [di], BZ_ZOPEN     ; z0 -128, flat, VOID, no flags
    mov word [di + 2], 0
.next:
    add bx, 4
    inc ax
    loop .cell
    inc word [bz_fr]
    pop cx
    loop .row
    call bz_wtail
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    ret
; bz_wtail - what a window owes after its nine cells (bz_fill's, bz_win9i's):
; bz_tsx and bz_tsy, the centre's surface, bz_wol and bz_ps.  -> AX = bz_nwin.
; Clobbers BX, CX, DX, SI, DI.
bz_wtail:
    test byte [bz_fhk], BZ_FH_CELL | BZ_FH_ENTER ; wave 9 (130.25.6.3): CELL first,
    jnz .fam                    ; ENTER last (out of line)
.go:
    xor ax, ax                  ; the centre's slopes, for step 2
    mov dx, ax
    mov si, bz_nbr + BZN_C
    mov cl, [si + 2]
    and cl, 0fh
    cmp cl, BZ_KFLOOR
    je .sl
    cmp cl, BZ_KGOAL
    jne .nfs
.sl:
    mov al, [si + 1]            ; sy : sx, signed nibbles
    or al, al
    jz .nosl                    ; (a flat floor, most: both 0 as they are)
    mov ah, al
    mov cl, 4
    shl al, cl
    sar al, cl                  ; AL = sx
    sar ah, cl                  ; AH = sy
    mov dl, ah
    cbw
    xchg ax, dx                 ; DX = sx
    cbw                         ; AX = sy
.nosl:
    mov [bz_tsx], dx
    mov [bz_tsy], ax
.slset:
    mov al, [bz_nbr + BZN_C + 2] ; the centre's SURFACE (whatever its kind): a
    mov cl, 4                   ; new one rebuilds the step's force, drag,
    shr al, cl                  ; brake and floor e (130.11.7.1)
    cmp al, [bz_surf]
    je .same
    call bz_surfset
.same:
    cmp byte [bz_wfl], 1        ; wave 3: bz_wol and bz_ps (a course with no
    jb .nowol                   ; prop has neither, so they stay 0); D3: a
    ja .split                   ; course with a split cell (bz_wfl, GF_SPLIT)
.wolf:
    call bz_wolf
.nowol:
    mov ax, [bz_nwin]
    ret
.split:
    call bz_wsplit              ; (out of the line: bz_nbh, bz_psp, bz_ps bit 3,
    test byte [bz_wfl], 1       ; and a split centre's slopes - before
    jz .nowol                   ; bz_wolf, whose bz_psync reads bz_psp)
    jmp short .wolf
.fam:                           ; a course with families: CELL (each family
    mov ax, BZ_HK_CELL          ; with an entry rewrites its elements' cells in
    call bz_fall                ; bz_nbr, never the grid, SPEC.md 130.25.7.2),
    push word [bz_wcen]         ; the window's own work, then ENTER when the
    call .go                    ; centre's owner changed to a family element
    pop bx                      ; BL = the owner (index + 1) before
    mov dx, [bz_wcen]           ; DL = it after, DH its kind (0: none)
    cmp dl, bl
    je .fx
    cmp dh, BZ_FK0
    jb .fx
    push ax
    mov bl, dl                  ; BX the element, DL its kind, AH bz_air
    mov dl, dh
    mov bh, 0
    dec bx
    mov ah, [bz_air]
    mov al, BZ_HK_ENTER
    call bz_fone
    pop ax
.fx:
    ret

; (bz_wtail's, out of its line: a centre neither FLOOR nor GOAL - a FIELD
; one's slopes at the ball's point, SPEC.md 130.28.5.1)
bz_wtail.nfs:
    cmp cl, BZ_KFIELD
    jne bz_wtail.nosl
    call bz_fh4
    jmp bz_wtail.slset

; =============================================================================
; SPEC.md 130.28: FIELD CELLS - a cell's floor a 17 x 17 table of section F
; through one of the square's eight symmetries.  bz_fsb (bz_cexp's) holds each
; table's offset in the course; BZ_FSYM's entry, 16 x the symmetry, the
; origin (the index of (0, 0)), the strides DU, DV and the two walks.
; =============================================================================

; bz_fhp - SI = a FIELD cell's 4 bytes (DS), DL = u, DH = v (0 .. 16), ES =
; the course -> AX = h4 there, 8 z0 + F[17 V + U] (quarter px); DI = that
; byte's offset in ES, BX = 8 x the symmetry (bz_fh4's).  Preserves CX, DX,
; SI, BP.  The shape is the +1's bits 0 - 3 with bit 7 its fifth (0 - 31).
bz_fhp:
    push si
    mov al, [si + 1]            ; shape (bits 0 - 3, 7) : symmetry (4 - 6)
    mov bl, al
    cbw                         ; AH = FFh when bit 7, the shape's fifth bit
    and ax, 100fh
    or al, ah                   ; AL = the shape, 0 - 31 (SPEC.md 130.28.2)
    cbw
    shl ax, 1
    mov di, ax
    mov di, [bz_fsb + di]       ; the table
    and bx, 70h                 ; BX = 8 x the symmetry: its BZ_FSYM entry
    shr bx, 1
    add di, [bz_fsymt + bx]     ; + the origin
    mov al, dl                  ; + u's walk: u DU (the walk's byte offset
    xor ah, ah                  ; from bz_fkp1, + 2u: under 256, BZ_FWALKS)
    shl ax, 1
    add al, [bz_fsymt + bx + 6]
    mov si, ax
    add di, [bz_fkp1 + si]
    mov al, dh                  ; + v's: v DV
    xor ah, ah
    shl ax, 1
    add al, [bz_fsymt + bx + 7]
    mov si, ax
    add di, [bz_fkp1 + si]
    pop si
    mov al, [si]                ; 8 z0 + the byte
    cbw
    shl ax, 1
    shl ax, 1
    shl ax, 1
    add al, [es:di]
    adc ah, 0
    ret

; bz_fh4 - the window centre, a FIELD cell, at the ball's integer point:
; BX = its h4 (step 6's floor), and bz_tsx, bz_tsy its slopes there - the
; forward differences F[i + DU] - F[i], F[i + DV] - F[i] (130.28.2).  SI =
; the centre.  ES = the course.  Clobbers AX, CX, DX, DI.
bz_fh4:
    mov si, bz_nbr + BZN_C
    mov dl, [bz_gx + 1]
    and dl, 15
    mov dh, [bz_gy + 1]
    and dh, 15
    call bz_fhp
    push ax
    mov cl, [es:di]
    xor ch, ch
    mov dx, di
    add di, [bz_fsymt + bx + 2]
    mov al, [es:di]
    xor ah, ah
    sub ax, cx
    mov [bz_tsx], ax
    mov di, dx
    add di, [bz_fsymt + bx + 4]
    mov al, [es:di]
    xor ah, ah
    sub ax, cx
    mov [bz_tsy], ax
    pop bx
    ret

; BZ_FSYM: a symmetry s (bit 0 MU, 1 MV, 2 SW) -> 8 bytes: the index of
; (0, 0), DU, DV, and u's walk and v's (the multiples of DU, DV, 0 - 16), each
; a BYTE, its table's offset from bz_fkp1
%macro BZ_FSYMENT 1
 %assign %%mu (%1) & 1
 %assign %%mv ((%1) >> 1) & 1
 %if (%1) & 4
  %assign %%o 17 * 16 * %%mu + 16 * %%mv
  %assign %%du 17 * (1 - 2 * %%mu)
  %assign %%dv 1 - 2 * %%mv
 %else
  %assign %%o 17 * 16 * %%mv + 16 * %%mu
  %assign %%du 1 - 2 * %%mu
  %assign %%dv 17 * (1 - 2 * %%mv)
 %endif
    dw %%o, %%du, %%dv
 %if %%du == 1
    db bz_fkp1 - bz_fkp1
 %elif %%du == -1
    db bz_fkm1 - bz_fkp1
 %elif %%du == 17
    db bz_fkp17 - bz_fkp1
 %else
    db bz_fkm17 - bz_fkp1
 %endif
 %if %%dv == 1
    db bz_fkp1 - bz_fkp1
 %elif %%dv == -1
    db bz_fkm1 - bz_fkp1
 %elif %%dv == 17
    db bz_fkp17 - bz_fkp1
 %else
    db bz_fkm17 - bz_fkp1
 %endif
%endmacro
bz_fsymt:
%assign bz_s 0
%rep 8
    BZ_FSYMENT bz_s
 %assign bz_s bz_s + 1
%endrep
%macro BZ_FWALK 1
 %assign bz_k 0
 %rep 17
    dw (%1) * bz_k
  %assign bz_k bz_k + 1
 %endrep
%endmacro
bz_fkp1:
    BZ_FWALK 1
bz_fkm1:
    BZ_FWALK -1
bz_fkp17:
    BZ_FWALK 17
bz_fkm17:
    BZ_FWALK -17
%if bz_fkm17 + 2 * 16 - bz_fkp1 > 255 || $ - bz_fsymt != 8 * 8 + 4 * 2 * 17
 %error "BZ_FSYM: a walk's byte offset (+ 2 x 16) must stay under 256, an entry 8 bytes"
%endif
; the lift's offsets: each window cell's (16 dx, 16 dy), bz_nbr's order
bz_fmap:
    db -16, -16, 0, -16, 16, -16
    db -16, 0, 0, 0, 16, 0
    db -16, 16, 0, 16, 16, 16

; bz_surfset - AL = the window centre's surface: [bz_surf] = it, bz_se =
; BZ_SURFTAB's entry for [bz_mat] on it (force, drag shift, brake, floor e),
; and bz_ftg rebuilt from its force, ftg[l] = (A l + 4) >> 3 (130.11.7.1);
; bz_dmask = 2^k - 1 for its drag shift k and bz_drx, bz_dry cut to it
; (130.16.3.1: its callers are bz_fill, on a change of the centre's surface,
; and bz_setmat, whose new material can change k on the same surface).
; A surface 4 - 15 is RESERVED and the tool refuses it: nothing is checked.
; DS = ours.  Clobbers AX, BX, CX, DX, DI.
bz_surfset:
    mov [bz_surf], al
    mov bl, [bz_mat]
    shl bl, 1
    shl bl, 1
    add bl, al
    xor bh, bh
    shl bx, 1
    shl bx, 1                   ; 4 (4 mat + surface)
    mov ax, [bz_surftab + bx]
    mov [bz_se], ax
    mov cl, ah                  ; wave 6 (130.16.3.1): the drag's mask, 2^k - 1
    mov al, 1                   ; (k 8: 0FFh; ice's 0: 0), and BOTH remainders
    shl al, cl                  ; CUT to it, the one place the mask changes
    dec ax
    mov ah, al
    mov [bz_dmask], al
    and [bz_drx], ax
    mov ax, [bz_surftab + bx + 2]
    mov [bz_se + 2], ax
    mov al, [bz_se]             ; the force at full ramp
    mov di, bz_ftg
    mov cl, 3
    jmp bz_ramp

; bz_fill's five grid rows, s - 2 .. s + 2: the first cell's k against the
; centre's (BZ_WRP: -1 for an even a, 0 for an odd one), the run, and the
; window cells in k order (a ascending)
BZ_WRP      equ 1
bz_wrt:
    dw 0, 1, bz_nbr + BZN_NW                            ; s - 2: a
    dw BZ_WRP, 2, bz_nbr + BZN_W, bz_nbr + BZN_N        ; s - 1: a - 1, a + 1
    dw -1, 3, bz_nbr + BZN_SW, bz_nbr + BZN_C, bz_nbr + BZN_NE ; s: a - 2, a, a + 2
    dw BZ_WRP, 2, bz_nbr + BZN_S, bz_nbr + BZN_E        ; s + 1: a - 1, a + 1
    dw 0, 1, bz_nbr + BZN_SE                            ; s + 2: a

; -----------------------------------------------------------------------------
; bz_place - the ball on bz_safe's centre (16 wx + 8, 16 wy + 8) on its floor,
; at rest and grounded, the window filled round it (130.10.7.1, step 7).
; bz_placeat: on the cell AL = wx, AH = wy (wave 4's flag respawn).  ES =
; the course.  Clobbers AX, BX, CX, DX, SI.
; -----------------------------------------------------------------------------
bz_place:
    mov ax, [bz_safe]
bz_placeat:
    push ax
    mov dl, ah
    xor ah, ah
    xor dh, dh
    mov cl, 4
    shl ax, cl
    add ax, 8
    mov [bz_gx + 1], ax
    shl dx, cl
    add dx, 8
    mov [bz_gy + 1], dx
    xor ax, ax
    mov [bz_gx], al
    mov [bz_gx + 3], al
    mov [bz_gy], al
    mov [bz_gy + 3], al
    mov [bz_gvx], ax
    mov [bz_gvy], ax
    mov [bz_gvz], ax
    mov [bz_air], al
    mov [bz_tube], al           ; out of any tube, off the platform (SPEC.md
    mov [bz_tseg], al           ; 130.12.6.5: a respawn changes no prop)
    mov [bz_onp], al
    mov [bz_tcnt], ax
    pop ax
    call bz_fill
    mov si, bz_nbr + BZN_C
    mov dx, 0808h
    call bz_h4
    jmp bz_setz

; -----------------------------------------------------------------------------
; bz_derive - the SCREEN state from (gx, gy, z) (SPEC.md 130.10.8):
;   bz_bx = gx - gy + (X0 - 8),  bz_by = (gx + gy) / 2 - z + (Y0 - 13)
; in 24.8 (fractions kept), and bz_vx, bz_vy = how far their low words moved.
; Clobbers AX, BX, CX, DX, SI, DI.
; -----------------------------------------------------------------------------
bz_derive:
    mov ax, [bz_gx]
    mov dx, [bz_gx + 2]
    mov si, [bz_gy]
    mov di, [bz_gy + 2]
    mov bx, ax
    mov cx, dx
    sub ax, si                  ; gx - gy
    sbb dx, di
    add ax, [bz_kx]
    adc dx, [bz_kx + 2]
    mov [bz_bx + 2], dx
    mov dx, [bz_bx]             ; DX = last step's low word
    mov [bz_bx], ax
    sub ax, dx
    mov [bz_vx], ax
    add bx, si                  ; (gx + gy) / 2
    adc cx, di
    shr cx, 1
    rcr bx, 1
    sub bx, [bz_gz]
    sbb cx, [bz_gz + 2]
    add bx, [bz_ky]
    adc cx, [bz_ky + 2]
    mov [bz_by + 2], cx
    mov ax, [bz_by]
    mov [bz_by], bx
    sub bx, ax
    mov [bz_vy], bx
    ret

; the products of bz_h4: T[(n & 15) << 4 | u] = n u, n -8 .. 7, u 0 .. 15
bz_prod:                        ; n u, n 0 - 7 (bz_h4: a negative n through ~n)
%assign bz_i 0
%rep 128
    db (bz_i >> 4) * (bz_i & 15)
 %assign bz_i bz_i + 1
%endrep

; the corner table, the model's own (bzcourse.inc, 130.10.7.3)
bz_ctab:
    BZ_CORNER_TABLE
; D3 (SPEC.md 130.24.7.3 - 130.24.7.4): the split cells' tables, the model's own
; (bzcourse.inc's, from bbcourse.OWNER, K_RECS and RAYS)
bz_swin:
    BZ_SPLIT_WIN
bz_srays:
    BZ_SPLIT_RAYS
; the bumpers' octant table, the model's own (bzcourse.inc, 130.12.6.3)
bz_otab:
    BZ_OCTANT_TABLE
; the materials' records and every material's force, drag, brake and floor e on
; every surface (bzcourse.inc, bbcourse.MATERIALS: SPEC.md 130.11.5.1, 130.11.6.2)
bz_mattab:
    BZ_MATTAB
bz_surftab:
    BZ_SURFTAB
bz_bokt:                        ; the boost's FLAT props (SPEC.md 130.16.4.1.1)
    BZ_BOKT
