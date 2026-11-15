; bzgame.inc - BONANZA's frame loop, simulation, camera, autopilot and
; instruments (SPEC.md 128.4 - 128.6).
;
; =============================================================================
; GUEST STATE A HARNESS READS (tests/bonanza_*.py; offsets are the package
; segment's, resolved through the listing or a re-assembly like Excitebike's)
; =============================================================================
;   bz_mode     byte   0 play, 1 benchmark (B), 2 replay (R, SPEC.md 128.11.12),
;                      3 the DEMO benchmark (D, 128.14.7.3): a replay for every
;                      log, step, identity and goal test (bz_mode >= 2) and a
;                      benchmark for bz_meas and the results (bit 0)
;   bz_fs       byte   1 while the bracket is up (mode set .. the loop's end)
;   bz_err      byte   0; 1 the mode was refused; 2 the display changed under us;
;                      3 a replay's log is another course's (SPEC.md 128.12.8)
;   bz_herc     byte   0 CGA, 1 Hercules
;   bz_S        word   the SHOWN start address, words, < 4096: (W*bz_R0 + bz_c0)
;                      mod 4096, written by bz_flip at bz_tf in the same frame
;   bz_R0       word   the shown window's top CARD row (2 lines CGA, 4 Hercules)
;   bz_c0       word   ...and its left WORD column (8 game px)
;   bz_bx,bz_by DWORD  the ball's top-left, world px in 24.8 fixed point:
;                      +0 the fraction byte, +1 the integer px as a WORD,
;                      +3 always 0.  DERIVED by physics from the ground
;                      position at the end of every step (bzphys.inc, SPEC.md
;                      128.10.8); the physics state is bzphys.inc's head
;   bz_crs      byte   the course played: K (bzcourse.inc's BZ_CRS_*), from
;                      bz_crsel (N) for a play, BZ_CRS_BENCH for B, the log's
;                      for R; a harness pokes it at bz_launch's entry
;   bz_mat      byte   the material played, 0 rubber, 1 steel, 2 glass
;                      (bonanza.asm bz_launch: M's for a play, the course's own
;                      for a benchmark, the log's for a replay)
;   bz_px,bz_py word   the integer px this frame drew the ball at (= the word at
;                      bz_bx+1 / bz_by+1 when the frame began its boxes)
;   bz_frm      word   the ROLL frame: PHY * 8 + (px & 7), PHY the vertical phase
;                      off the GROUND line G = the integer part of (gx + gy) / 2:
;                      G & 7 on the CGA, (G & 6) | (py & 1) on the Hercules, + 2
;                      ((mct >> 2) & 1) mod 8 while STUNNED (SPEC.md 128.11.9.2)
;   bz_spr      byte   the SPRITE drawn: 0 - 63 roll frame bz_frm, 64 + k squash
;                      k (0, 1), 68 + k shatter k (0 - 3), 72 rubber's stretch
;                      (bz_sprite); copy py & 1 of a squash, shatter or stretch
;                      entry, at shift px & 3
;   bz_shc      byte   1: the shadow is a CANDIDATE this frame (airborne over a
;                      FLOOR or GOAL, 2 px or more up, the centre's OCCG clear,
;                      SPEC.md 128.11.9.4); bz_spy word its first line
;   bz_snv      byte   1: the shadow is DRAWN this frame (bz_mkboxes: the
;                      candidate, less the OCC rule's drop), at bz_spy, shift px & 3
;   bz_vx,bz_vy word   the SCREEN velocity, signed, 1/256 px a step: how far
;                      bz_bx, bz_by moved in the last step (physics derives
;                      both, bzphys.inc; a respawn's is 0)
;   bz_frames   word   frames presented this bracket (bz_presented counts)
;   bz_mfr      word   ...of which MEASURED (a benchmark's frames but a full
;                      write; play and a replay measure nothing)
;   bz_ncol     word   columns written (a column split round the boxes calls
;                      bz_col more than once and counts once); bz_nrow word bz_row
;                      calls; bz_nfull word full writes; bz_tos word
;                      retrace-wait timeouts
;   bz_miss     word   measured frames whose period passed 1.5 refreshes (a
;                      missed retrace: the frame showed for two or more)
;   bz_fmax     DWORD  the longest measured frame period, PIT counts
;   bz_acc      7 DWORDS, PIT counts summed over the measured frames, one per
;                      part: 0 sim+camera (bz_t0..bz_ts), 1 box compose and the
;                      occluder pass (..bz_tr), 2 rows (..bz_tw), 3 retrace wait,
;                      IDLE (bz_tv..bz_tf), 4 flip + columns (..bz_tb, and every run of
;                      column rows written after a box), 5 box write (bz_tb ..
;                      bz_presented less those runs, and a LEAD), 6 the WHEEL,
;                      idle (bz_tw..bz_tv, wave 3, appended so 0 - 5 keep their
;                      numbers: SPEC.md 128.12.5.6).  CPU clocks = counts x 4.
;   bz_cmode    byte   the camera MODE (SPEC.md 128.11.11.1): 0 GLIDE, 1 TRICKLE
;                      (FOLLOW is gone).  C toggles it, in play and on the desktop;
;                      it persists across plays (bss, never reset).  The benchmark
;                      runs GLIDE whatever it says and leaves it alone
;   bz_lax,bz_lay 16 bytes each: LATTICE's axes (wave 6b, SPEC.md 128.17.6.2),
;                      across and down, BZL_* offsets: +0 s (the pan's sign),
;                      +1 last, +2 fast, +3 since (across), +4 held (the heavy
;                      rule's withheld steps running), +6 tgt word, +12/+14 the
;                      band's bounds (words, the tracked point's px or lines)
;   bz_late     word   BOXES the beam overtook (SPEC.md 128.11.10.3, bz_latechk on
;                      every box of a TIMED frame - a benchmark's measured one, or
;                      a harness's bz_tpoke - never a full write): a box not
;                      STARTED before the beam reached its first window line (line
;                      0 for a first box at window row 0, whose column rows went
;                      first) or not ENDED before it reached its last
;   bz_nocf     word   frames the occluder pass ran (gated ON: the centre's cell
;                      has OCC or the ball was poked; ONE walk a frame, laid into
;                      every box, SPEC.md 128.11.10.2)
;   bz_nlay     word   records the pass laid back
;   bz_n2bx     word   frames with two or more boxes;  bz_n3bx three or more
;   bz_nshd     word   frames whose shadow was drawn (bz_snv)
;   bz_wcom .. bz_wtmin words, wave 3's (SPEC.md 128.12.5.6): commits, overruns,
;                      lanes late, LEADs, skipped wheels, contact groups,
;                      platform boxes, deferred contact lanes, heavy frames, rows
;                      and columns withheld, edge releases, the trim's lowest;
;                      bz_npwt word, wave 3b's: the platform's box WAITED a
;                      frame (SPEC.md 128.13.4.3; bz_ndef counts it too)
;   bz_res      byte   1 = the bz_r* copy below holds a finished benchmark
;   bz_rframes, bz_rmfr, bz_rncol, bz_rnrow, bz_rnfull, bz_rmiss, bz_rfmax,
;                      bz_racc, bz_rlate, bz_rnocf, bz_rnlay, bz_rn2bx, bz_rn3bx,
;                      bz_rnshd, bz_rwcom .. bz_rnpwt: that copy, the same
;                      layout as bz_frames .. bz_npwt
;   bz_nbox     word   this frame's boxes (0 - 4), bz_boxes the descriptors (BZ_BOXD
;                      bytes each, bzvideo.inc), SORTED by first line
;   bz_csp      4 words the entering column's split rows: before box i, the
;                      column's rows [bz_cdone, bz_csp[i]) are written (i > 0;
;                      box 0's went before bz_tb); bz_cdone word the rows written
;                      so far (H on a frame with no entering column)
;   bz_row0     byte   1: this frame's FIRST box is at window row 0 and the
;                      column's rows down to its last line went first (bz_csplit)
;
; THE REPLAY LOG (SPEC.md 128.11.12) is bonanza.asm's bz_rlog; the recorder's
; and the player's cells are bz_rptr (the next pair), bz_rk and bz_rn (the
; current run: its key byte and count - in a replay the count LEFT), bz_rruns
; (a replay's runs not yet read), bz_rtr (1: truncated) and bz_rtrs (DWORD, the
; steps recorded when it was).
;
; AT bz_presented THE CARD HOLDS THE WINDOW EXACTLY: every word of the W x H
; window at bz_S is the course's, with the shadow at (bz_px, bz_spy) when
; bz_snv (AND only, shadow (spy & 1, px & 3) of the ball part), then the ball's
; sprite bz_spr at (bz_px, bz_py) composited (shift bz_px & 3), and the
; occluder records SPEC.md 128.10.4.4's rule lays at the ball's s_b, z_b and air
; flag laid back over both inside the ball's footprint (bzvideo.inc bz_occ).
; bonanzaring decodes it there.
;
; THE FRAME (SPEC.md 128.4), marks as GLOBAL labels in this order:
;   bz_t0 .. bz_ts .. bz_tr .. bz_tw .. bz_tv .. bz_tf .. bz_tb [.. bz_tc] ..
;   bz_presented
; and bz_col / bz_row (bzvideo.inc) are the writers' entries.  Wave 3
; (bzwheel.inc, SPEC.md 128.12.4.4): bz_t0's RULE 0 is bz_foot (the ball's
; screen state and new footprints), bz_props (the lanes' walk, the contact
; group, bz_heavy), then the camera; the WHEEL commits lanes between bz_tw
; and bz_tv, in the retrace wait's time; the LEAD follows the column and the
; boxes, before bz_presented.  The boxes are
; written in the order of their first lines, INTERLEAVED in raster order with
; the entering column's rows (SPEC.md 128.11.10.3): the rows above the first
; box between bz_tf and bz_tb, then each box, each preceded by the column's
; rows that end above it (bz_tcmid, billed to the box write: no mark), and
; after the last box the rest of the column at bz_tc.  A first box
; at window row 0 has no column rows above it: then the column's rows down to
; that box's LAST line go first (SPEC.md 128.9 item 6).  With no box, or a box
; holding a cell of the column, the whole column goes first.
; =============================================================================

; THE CLOCK.  Excitebike's (SPEC.md 102, xb_clk_sample's shape): PIT channel 0
; counts DOWN from BZ_SUB once a FASTTICK sub-tick, and a sample that reads a
; LARGER count than the last one has seen one reload.  Exact while no stretch
; between two samples reaches a sub-tick: everything here samples at least
; every ~30k clocks (each mark, each row written, the retrace spin).
; =============================================================================

BZ_MAXR     equ 2               ; rows the camera may step a frame (SPEC.md 128.2)
BZ_MAXC     equ 1               ; ...and columns
BZ_WC       equ 40              ; the window's word columns, W: the CGA's ...
BZ_WH       equ 45              ; ...and the Hercules' (bz_vinit's bz_W)
BZ_CSAFE    equ 16              ; the ground line's edge fallback: the ball's
                                ; centre within this many lines of the window's
                                ; top or bottom latches cy on the ball (128.16.7)
BZ_NPART    equ 7               ; the frame's measured parts (the marks' gaps)
BZ_NFACE    equ 6               ; ...of which the face shows (the wheel's is the rows')
BZ_BENCH    equ 1200            ; the benchmark's frames (SPEC.md 128.6)
BZ_STEPS    equ 8               ; simulation steps a frame, at most
BZ_SUB      equ 21845           ; PIT counts in one FASTTICK sub-tick
BZ_ACC      equ 8               ; the AUTOPILOT's (bz_auto): an arrow is wanted when
BZ_VMAX     equ 512             ; the screen velocity is BZ_ACC / 2 off the one it
                                ; wants, 8/256 px a step per px of distance and at
                                ; most BZ_VMAX.  The ball itself is physics v1's
                                ; (bzphys.inc, SPEC.md 128.10.7): its speeds are
                                ; BZ_VMAXG, BZ_VZMAX (bzcourse.inc), and a footprint
                                ; that moves past one box takes 128.4's two-box path
BZ_REACH    equ 12              ; the autopilot's waypoint radius, px
BZ_KSC_F    equ 21h             ; the F key's make code
BZ_KSC_B    equ 30h             ; ...and B's
BZ_KSC_C    equ 2eh             ; ...and C's: the camera mode (SPEC.md 128.9)
BZ_KSC_BKSP equ 0eh             ; ...and Backspace's: RETURN (SPEC.md 128.14.4.5)
BZ_KSC_R    equ 13h             ; ...and R's: the replay (SPEC.md 128.11.12.2)
BZ_KSC_G    equ 22h             ; ...and G's: the tour (SPEC.md 128.14.3.1)
BZ_KSC_P    equ 19h             ; ...and P's: PAUSE (SPEC.md 128.14.4.7)
BZ_KSC_D    equ 20h             ; ...and D's: the demo benchmark (128.14.7.3)
BZ_CMODES   equ 2               ; GLIDE, TRICKLE (SPEC.md 128.11.11.1)
; GLIDE's "faster than 4 px a FRAME" across is the ball's TRAVEL over the last
; FOUR frames (SPEC.md 128.11.11.1), in the 24.8 low word of bz_bx: rate-proof,
; where wave 1's |v| against a per-card constant assumed the full refresh.
; bbcourse.Glide (GLIDE_FX) is the model.  Wave 6b deletes the ring's y half:
; LATTICE's rows never read it (SPEC.md 128.17.6.2).
BZ_GTRX     equ 4 * 4 * 256     ; 4 px a frame, four frames
; LATTICE (wave 6b, SPEC.md 128.17.6.2): an axis's STATE (bz_lax across, bz_lay
; down; bbcourse.LatAxis's) ...
BZL_S       equ 0               ; byte: the running pan's sign, 1 / -1, 0 at rest
BZL_LAST    equ 1               ; byte: the sign of the last pan that MOVED the window
BZL_FAST    equ 2               ; byte: 1 the pan's rate latch is set
BZL_SINCE   equ 3               ; byte: frames since the pan's last column (across)
BZL_HELD    equ 4               ; byte: steps the heavy rule withheld since it stepped
BZL_SH      equ 5               ; byte: log2 of the unit u (across 3, down bz_lsh)
BZL_TGT     equ 6               ; word: the pan's target position
BZL_MX      equ 8               ; word: the position's range's top (cmax, rmax)
BZL_K       equ 10              ; word: its constants' row in bz_klat (the card's)
BZL_BLO     equ 12              ; word: the BAND at the window's position, in the
BZL_BHI     equ 14              ; tracked point's px or lines: P u + lo, P u + hi
                                ; (bz_lband, after every move and at rest's reset)
BZL_SIZE    equ 16
; ... and its CONSTANTS (bz_klat: across on the CGA, on the Hercules, down;
; bbcourse.lat_consts), in the axis's px or lines
BZK_A       equ 0               ; the band margin A: lo = A - Hr after a pan +
BZK_WPA     equ 2               ; Wp - A: hi = Wp - A + Hr after a pan -
BZK_HR      equ 4               ; the return hysteresis Hr
BZK_T       equ 6               ; the lead placement T (the stop going +)
BZK_WPT     equ 8               ; Wp - T (the stop going -)
BZK_EF      equ 10              ; the urgent edge Ef ...
BZK_WPE     equ 12              ; ...and Wp - Ef
BZK_M       equ 14              ; u S - 1: the lattice's spacing less one, a
                                ; power of two less one (64 across, 32 down)
BZK_COLS    equ 16              ; byte: 1 across (the column cadence, since)
BZK_SIZE    equ 17
%if BZ_LAX_S * 8 != 64 || BZ_LAY_SL != 32
 %error "bz_lat's lattice is a mask: u S is 64 px across and 32 lines down"
%endif
%if BZ_SCR_HOLD != 8
 %error "bz_camera's script indexes its cycle by (count >> 3) & 7: holds of 8"
%endif
%if BZ_LAH1 > 127 || BZ_LAH2 > 127
 %error "bz_lhv's caps are bytes"
%endif
%if BZ_PF_NEARR != BZ_PF_NEARL << 1 || BZ_PF_NEARB != BZ_PF_NEART << 1 || BZ_PF_NEARB > 80h
 %error "bz_lhv shifts the heading bit: bz_pflag's R = L << 1 and B = T << 1, in a byte"
%endif
BZ_K_L      equ 1               ; bz_keys: the arrows held
BZ_K_R      equ 2
BZ_K_U      equ 4
BZ_K_D      equ 8
BZ_LIVE     equ 84              ; bytes of bz_frames .. bz_npwt (the results copy)
BZ_SPR_SQ   equ 64              ; bz_spr: squash k is 64 + k ...
BZ_SPR_SHA  equ 68              ; ...and shatter k 68 + k (roll frames 0 - 63)
BZ_SPR_STR  equ 72              ; ...and rubber's stretch 72 (wave 6, 128.16.4.4)
BZ_NBOXMAX  equ 4
; THE EARLY STEP (bz_early): a step that is already due by the clock runs in
; the retrace wait's idle time instead of at the next frame's top.  On unless
; the build defines BZ_NOEARLYSTEP (`nasm -DBZ_NOEARLYSTEP`: the A/B, and the
; bytes of the tree before it).
%ifndef BZ_NOEARLYSTEP
 %define BZ_EARLYSTEP
%endif
BZ_EROOM    equ 8000            ; PIT counts (32k clk) the wait must still hold: the
                                ; worst step MEASURED (21.8k clk, a bz_win9f refill
                                ; and a tick's ISR in it), the 16 lines the last
                                ; wait's sample may sit inside its sync (4.9k), a
                                ; tick more and bz_vr's way to its first read
BZ_ESYNC    equ 1400            ; ...and a frame this little past a sync may still
                                ; present in it (bz_vr's "already high"): no step

%macro BZ_GAME_VARS 0
VAR bz_mode,1
VAR bz_fs,1
VAR bz_err,1
VAR bz_herc,1
VAR bz_res,1
VAR bz_full,1
VAR bz_meas,1
VAR bz_tpoke,1                  ; a harness's: time this play's boxes too (bz_wbox;
                                ; nothing in the package writes it, bss is 0)
VAR bz_first,1
VAR bz_oldv,1
VAR bz_keys,1
VAR bz_kmap,KEYMAP_BYTES        ; the frame's key map (OSAPI_KEY_MAP, bz_exitchk)
VAR bz_lsh,1
VAR bz_row0,1                   ; 1: this frame's box is at window row 0 (bz_csplit)
VAR bz_r0p,1                    ; 1: a box starts at the new window's first line
                                ; (bz_r0pend): bz_vr shuts interrupts at the rise
VAR bz_vedge,1                  ; 1: bz_vr saw the sync RISE (not already high)
VAR bz_crs,1                    ; the course K: BZ_CRS_FIRST to play, BZ_CRS_BENCH
                                ; for the benchmark (bzcourse.inc)
VAR bz_mapsh,1                  ; the course's MAPSH (bz_crshdr): 4 or 5
VAR bz_cmode,1                  ; the camera mode: 0 GLIDE, 1 TRICKLE
VAR bz_cuse,1                   ; ...the one this frame used (a benchmark: GLIDE)
VAR bz_ckey,1                   ; FFh while C was down last frame (the edge)
VAR bz_bkey,1                   ; ...and Backspace (RETURN: one press, one step)
VAR bz_gfast,1                  ; GLIDE: 1 while the ball is FAST across: its
                                ; travel over four frames (128.11.11.1)
VAR bz_tri,1                    ; ...the travel ring's index (mod 4), and
VAR bz_scnt,1                   ; bz_camscr's frame count: bits 0 - 5 the cycle's
                                ; frame, bit 7 set while the script runs (its
                                ; clearing is a cut, SPEC.md 128.17.6.7)
VAR bz_blk,1                    ; 1: the card's video is gated (bz_blank)
VAR bz_trx,8                    ; the ring: the low word of bz_bx at the end of
                                ; each of the last four frames
VAR bz_lax,BZL_SIZE             ; LATTICE's axes (wave 6b, SPEC.md 128.17.6.2):
VAR bz_lay,BZL_SIZE             ; across and down (BZL_*)
VAR bz_cgz,2                    ; wave 6 (128.16.7): the GROUND height zg, whole
                                ; px, the last frame's (held over no floor)
VAR bz_clat,2                   ; ...the edge fallback's LATCH: +1 1 while
                                ; latched, +0 bz_nland's low byte when it tripped
VAR bz_S,2
VAR bz_R0,2
VAR bz_c0,2
VAR bz_R0n,2
VAR bz_c0n,2
VAR bz_dr,2
VAR bz_dc,2
VAR bz_bx,4
VAR bz_by,4
VAR bz_vx,2
VAR bz_vy,2
VAR bz_px,2
VAR bz_py,2
VAR bz_frm,2
VAR bz_wp,2
VAR bz_spy,2                    ; the shadow's first line (bz_sprite)
VAR bz_smsk,2                   ; the sprite's mask, row 0, in the ball part ...
VAR bz_sfd,2                    ; ...and its frame's distance from it
VAR bz_shm,2                    ; the shadow's mask (shadow (spy & 1, px & 3))
VAR bz_wtop,2                   ; the new window's top line (bz_mkboxes)
VAR bz_spr,1                    ; the sprite (bz_frm's head), its last frame's,
VAR bz_ospr,1
VAR bz_shc,1                    ; the shadow: a candidate; drawn this frame;
VAR bz_snv,1                    ; drawn last frame (the old footprint's)
VAR bz_sov,1
VAR bz_ohold,1                  ; 1: the old footprints are this frame's (bz_mkboxes)
VAR bz_ogate,1                  ; 1: the occluder pass runs this frame
VAR bz_grp,1                    ; bz_addbox: the box's group (0 the ball's)
; the replay log's recorder and player (SPEC.md 128.11.12)
VAR bz_rptr,2                   ; the next run's pair in bz_rlog
VAR bz_rruns,2                  ; a replay: the runs not yet read
VAR bz_rtrs,4                   ; the steps recorded, when TRUNCATED
VAR bz_rk,1                     ; the current run: its key byte, its count (a
VAR bz_rn,1                     ; replay: the count left)
VAR bz_rtr,1                    ; 1: the log is TRUNCATED, nothing more recorded
VAR bz_rt,1                     ; the current run's tilt byte (a TILT log's,
                                ; SPEC.md 128.14.8.3; 88h a keyboard log's)
; the live instruments, then their copy: one layout (BZ_LIVE bytes)
VAR bz_frames,2
VAR bz_mfr,2
VAR bz_ncol,2
VAR bz_nrow,2
VAR bz_nfull,2
VAR bz_miss,2
VAR bz_fmax,4
VAR bz_acc,4 * BZ_NPART
VAR bz_late,2
VAR bz_nocf,2                   ; boxes composed with the occluder pass gated ON
VAR bz_nlay,2                   ; records the pass laid back (SPEC.md 128.10.8)
VAR bz_n2bx,2                   ; frames with two boxes or more (SPEC.md 128.11.10)
VAR bz_n3bx,2                   ; ...three or more
VAR bz_nshd,2                   ; frames with the shadow drawn (128.11.9.4)
VAR bz_wcom,2                   ; wave 3 (SPEC.md 128.12.5.6): the wheel's commits
VAR bz_wover,2                  ; ...those that ended past their deadline
VAR bz_wlate,2                  ; ...lanes due and shown for BZ_WLAG frames
VAR bz_wlead,2                  ; ...LEAD commits
VAR bz_wskip,2                  ; ...frames whose candidates the wheel skipped
VAR bz_ncon,2                   ; contact groups (a lane, a must-draw rotor, the slab)
VAR bz_npbx,2                   ; ...of which the platform's box
VAR bz_ndef,2                   ; contact lanes that WAITED (display only)
VAR bz_nhvy,2                   ; heavy frames (GLIDE, 128.12.7)
VAR bz_nwr,2                    ; ...the rows they withheld
VAR bz_nwc,2                    ; ...and the columns
VAR bz_nhedge,2                 ; ...heavy frames whose edge clause released an axis
VAR bz_wtmin,2                  ; the trim's lowest (100 when it never fell)
VAR bz_npwt,2                   ; wave 3b: the platform's box WAITED (128.13.4.3)
VAR bz_rframes,2
VAR bz_rmfr,2
VAR bz_rncol,2
VAR bz_rnrow,2
VAR bz_rnfull,2
VAR bz_rmiss,2
VAR bz_rfmax,4
VAR bz_racc,4 * BZ_NPART
VAR bz_rlate,2
VAR bz_rnocf,2
VAR bz_rnlay,2
VAR bz_rn2bx,2
VAR bz_rn3bx,2
VAR bz_rnshd,2
VAR bz_rwcom,2
VAR bz_rwover,2
VAR bz_rwlate,2
VAR bz_rwlead,2
VAR bz_rwskip,2
VAR bz_rncon,2
VAR bz_rnpbx,2
VAR bz_rndef,2
VAR bz_rnhvy,2
VAR bz_rnwr,2
VAR bz_rnwc,2
VAR bz_rnhedge,2
VAR bz_rwtmin,2
VAR bz_rnpwt,2
VAR bz_tos,2
; the clock
VAR bz_subs,2
VAR bz_pitl,2
VAR bz_msubs,2
VAR bz_mpit,2
VAR bz_lsubs,2
VAR bz_ppit,2                   ; the last frame's bz_presented mark (bz_mpit, bz_msubs
VAR bz_psubs,2                  ; then): a measured frame's period is this one less it
VAR bz_mlim,2
VAR bz_vsubs,2                  ; the retrace wait's last sample (bz_latechk)
VAR bz_vpit,2
VAR bz_lblank,2
; the course, from its part's header (bonanza.asm bz_crshdr, SPEC.md 128.10.5)
VAR bz_cols,2                   ; COLS, word columns
VAR bz_brows,2                  ; BROWS, block rows
VAR bz_rowb,2                   ; ROWB = 2 COLS (the box compose's copy)
VAR bz_goff,2                   ; GRIDOFF: the BZG1 header in the course part
VAR bz_x0,2                     ; X0, Y0: the projection's origin, px
VAR bz_y0,2
VAR bz_nway,2                   ; the route: NWAY waypoints at bz_wayoff in the
VAR bz_wayoff,2                 ; course part (the autopilot's, 128.10.11.1)
; the parts' segments and the card
VAR bz_cseg,2
VAR bz_bseg,2                   ; the sprite's ball part: bz_bsegs[bz_mat]
VAR bz_bsegs,2 * BZ_NMAT        ; wave 4 (SPEC.md 128.14.4.7): each material's
                                ; ball part, 0 when this launch did not fetch it
VAR bz_hidn,1                   ; the frame's HIDDEN ball: bz_tube OR bz_hid
                                ; (the display's test, set after the steps)
VAR bz_vseg,2
VAR bz_fsi,FSI_SIZE
VAR bz_W,2
VAR bz_H,2
VAR bz_rb,2
VAR bz_rl,2
VAR bz_bend,2
VAR bz_crtc,2
VAR bz_cmax,2
VAR bz_rmax,2
VAR bz_vrport,2
VAR bz_vrbits,2
VAR bz_vrlim,2
VAR bz_ccol,2
VAR bz_cdone,2                  ; the column's rows written (bz_tb)
VAR bz_csp,2 * BZ_NBOXMAX       ; ...before each box (bz_csplit)
; the footprints, as RECTS of four words, x0 x1 (word columns) y0 y1 (lines),
; inclusive: the ball's and the shadow's, old (last frame's) and new
VAR bz_ofx0,2                   ; the ball's old
VAR bz_ofx1,2
VAR bz_ofy0,2
VAR bz_ofy1,2
VAR bz_sox0,8                   ; the shadow's old (bz_sov)
VAR bz_nfx0,2                   ; the ball's new
VAR bz_nfx1,2
VAR bz_nfy0,2
VAR bz_nfy1,2
VAR bz_snx0,8                   ; the shadow's new (bz_snv)
VAR bz_ur,8                     ; bz_union's
VAR bz_gr,32                    ; the frame's box rects, before the clip
VAR bz_nbox,2
VAR bz_opx,2                    ; the ball's px, py last frame (the idle test)
VAR bz_opy,2
VAR bz_boxp,2                   ; bz_addbox: the next box's record in bz_boxes
VAR bz_sgr,2                    ; bz_mkboxes: the shadow group's first rect in bz_gr
VAR bz_xlo,2                    ; bz_boxw's copy of a box's overlap band
VAR bz_xa,2
VAR bz_xb,2
VAR bz_xact,2
VAR bz_bw,2
VAR bz_bstep,2                  ; bz_boxw: buffer step from a line's end to the next
VAR bz_wtab,10                  ; W * dr for dr = -2 .. 2 (bz_tf's incremental S)
VAR bz_imin,2                   ; bz_blit: the rows and bytes it draws, the
VAR bz_bly,2                    ; sprite's first line and mask
VAR bz_blm,2
VAR bz_fmp,2                    ; bz_boxc's fill: the run's map entry, buffer
VAR bz_fbp,2                    ; line, line word in a block, lines left
VAR bz_flo,2
VAR bz_fln,2
VAR bz_kmin,2
VAR bz_olo,2                    ; bz_occ (SPEC.md 128.10.8 item 1, 128.11.10.2):
VAR bz_ohi,2                    ; the lines [lo, hi) of the footprint inside the
VAR bz_ozk,2                    ; window, z_b + m, the block row's first line,
VAR bz_obr,2                    ; the first of its lines in [lo, hi), their
VAR bz_of,2                     ; count and 2 x the first's place in the block,
VAR bz_on,2                     ; its map row, and the block being laid
VAR bz_ofl2,2
VAR bz_omrow,2
VAR bz_oblk,2
VAR bz_omsk,16                  ; bz_oand: a block word's laid masks, ANDed
VAR bz_okt,1                    ; the 4-byte record (SPEC.md 128.15.5): bz_ozk
                                ; holds s_b + SB; kt = clamp(z_b + m - TB) (bz_occ)
VAR bz_osbias,2                 ; SB sign-extended, TB, MTAB (bz_crshdr)
VAR bz_otb,2
VAR bz_mtab,2
VAR bz_boxes,BZ_NBOXMAX * BZ_BOXD
VAR bz_boxbuf,4 * BZ_BOXB          ; four box buffers (SPEC.md 128.11.10.1),
                                ; whose first 512 bytes hold BZ_HTAB at a
                                ; Hercules launch, before the bracket (128.11.3)
BZ_WHEEL_VARS                   ; wave 3's lanes and wheel (bzwheel.inc)
%ifdef BZ_EARLYSTEP
VAR bz_estp,1                   ; 1: an early step ran and its frame is not presented yet
VAR bz_ersp,1                   ; ...and it respawned the ball (the next frame's bz_resp)
VAR bz_nearly,2                 ; early steps this play (an instrument: nothing reads it)
VAR bz_noearly,1                ; a harness's: no early step (a row whose oracle reads the
                                ; ball at bz_tf / bz_presented needs the state AS DRAWN there;
                                ; nothing in the package writes it, bss is 0)
%endif
%if bz_rframes - bz_frames != BZ_LIVE || bz_npwt + 2 != bz_rframes || bz_sox0 != bz_ofx0 + 8 || bz_snx0 != bz_nfx0 + 8 || bz_nfx0 != bz_sox0 + 8
 %error "bz_play copies the instruments and the footprints as blocks: their layout moved"
%endif
%endmacro

; -----------------------------------------------------------------------------
; bz_clk_sample - the sub-tick clock (DS = ours).  Preserves all but the flags.
; -----------------------------------------------------------------------------
bz_clk_sample:
    push ax
    pushf
    cli
    xor al, al
    out 43h, al                 ; latch channel 0
    in al, 40h
    mov ah, al
    in al, 40h
    xchg al, ah
    popf
    cmp ax, [bz_pitl]
    jbe .same
    inc word [bz_subs]          ; the count went UP: one reload
.same:
    mov [bz_pitl], ax
    pop ax
    ret

; -----------------------------------------------------------------------------
; bz_mark - a frame mark: the PIT counts since the last mark go to part BX/4's
; accumulator (bz_acc + BX) when this frame is measured, and the mark becomes
; the base.  A PLAY and a REPLAY measure nothing (bz_meas is 0 there, bz_camera)
; and read no base: their mark is the clock sample alone, ~0.3k clocks where it
; was ~0.55k.  A benchmark's (B, D) is ~0.7k of its own on MartyPC's 8088 (the
; latch, ~0.27k, and the 32-bit sum), billed to the part it closes: the small
; parts' means read that much high, and a benchmark's busy time ~4-5k above
; play's.  The frame's PERIOD is not summed here: bz_presented takes it once,
; its mark less the last frame's (the same counts: the marks' gaps telescope).
; Preserves all but the flags.
; -----------------------------------------------------------------------------
bz_mark:
    test byte [bz_mode], 1
    jz bz_clk_sample            ; a play, a replay: the sample, no base
    push ax
    pushf                       ; (bz_clk_sample, inline: a benchmark's frame
    cli                         ; has six or seven marks)
    xor al, al
    out 43h, al
    in al, 40h
    mov ah, al
    in al, 40h
    xchg al, ah
    popf
    cmp ax, [bz_pitl]
    jbe .same
    inc word [bz_subs]
.same:
    mov [bz_pitl], ax
    xchg ax, [bz_mpit]          ; AX = the last mark's count; this one the base
    cmp byte [bz_meas], 0
    je .base
    push cx
    push dx
    sub ax, [bz_pitl]           ; the phase moved (signed: the count runs down,
    cwd                         ; and |it| < BZ_SUB < 32,768) ...
    mov cx, [bz_subs]
    sub cx, [bz_msubs]          ; ...+ the whole sub-ticks: 0 on most marks and
    jcxz .ph                    ; 1 on most of the rest, so adds, not a MUL
.sub:
    add ax, BZ_SUB
    adc dx, 0
    loop .sub
.ph:
    add [bz_acc + bx], ax
    adc [bz_acc + bx + 2], dx
    pop dx
    pop cx
.base:
    mov ax, [bz_subs]
    mov [bz_msubs], ax
    pop ax
    ret

; -----------------------------------------------------------------------------
; bz_r0pend - [bz_r0p] = 1 when this frame's FIRST box (the boxes are sorted
; by first line, bz_mkboxes) starts at the NEW window's first line (SPEC.md
; 128.9 item 6's box at window row 0), else 0.  Asked before the retrace wait,
; in its idle time.  bz_vr then shuts interrupts at the sync's rise and bz_tb
; opens them after THAT box (SPEC.md 128.11.10.3: every later box and column
; row runs with interrupts on): the row-0 box's deadlines leave ~2.7k clocks
; on the CGA (its box writer is ~1.6x slower than the beam), and the final pass
; of wave 1 measured the one late box of the row-0 probe to be a FASTTICK ISR
; (~2.9k clocks) landing inside that stretch.  ~13k clocks (2.8 ms) shut, on
; such frames only: under a FASTTICK sub-tick, so no tick is lost, and under an
; 8250's byte at 2,400 baud.  Preserves all but the flags.
; -----------------------------------------------------------------------------
bz_r0pend:
    push ax
    mov byte [bz_r0p], 0
    cmp word [bz_nbox], 0
    je .out
    mov ax, [bz_wtop]
    cmp ax, [bz_boxes + 2]      ; the first box's first line
    jne .out
    mov byte [bz_r0p], 1
.out:
    pop ax
    ret

; -----------------------------------------------------------------------------
; bz_latechk - SPEC.md 128.9 item 6 for EVERY box (128.11.10.3): CF = 1 if NOW
; is later than the beam reaching window line AX.  The beam is reckoned from the
; retrace wait's clock sample ([bz_vsubs], [bz_vpit]): when the wait saw the
; sync RISE ([bz_vedge]) the sample is at most BZ_VLAT counts after its start
; (bz_vr), so 16 lines of sync less BZ_VLAT are still to come; when the sync
; was already high it may have been anywhere in its 16 lines, and its END is
; the late case.  Then [bz_lblank] counts of blank and AX window lines (76
; counts a CGA line, 63 a Hercules one; both round toward LATE).  Preserves
; all but the flags.
; -----------------------------------------------------------------------------
%if BZ_LINES + 16 > 255
 %error "bz_latechk takes 64 n from a line count under 256"
%endif
bz_latechk:
    push ax
    push bx
    push dx
    mov bx, [bz_lblank]         ; BX: the counts the beam takes to get there
    cmp byte [bz_vedge], 0
    je .lv
    add ax, 16                  ; the sync's lines, less BZ_VLAT: the sample
    sub bx, BZ_VLAT             ; came up to BZ_VLAT after the rise
.lv:
    mov dx, ax                  ; (n lines, under 256: a window's and the sync's)
    mov ah, al
    xor al, al
    shr ax, 1
    shr ax, 1                   ; 64 n
    cmp byte [bz_herc], 0
    jne .h
    shl dx, 1
    shl dx, 1
    add ax, dx                  ; 68 n
    shl dx, 1
    add ax, dx                  ; 76 n: CGA lines
    jmp short .b
.h:
    sub ax, dx                  ; 63 n: Hercules lines
.b:
    add bx, ax
    call bz_clk_sample
    mov ax, [bz_subs]
    sub ax, [bz_vsubs]          ; whole sub-ticks since (0 or 1: a sub-tick is
    mov dx, [bz_vpit]           ; longer than a refresh)
    sub dx, [bz_pitl]           ; + the phase moved (the count runs down)
    cmp ax, 1
    ja .late
    jb .el
    add dx, BZ_SUB
.el:                            ; DX = the counts since the retrace was seen
    cmp bx, dx                  ; CF = the beam got there first
    jmp short .out
.late:
    stc
.out:
    pop dx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; bz_play - the frame loop, until Esc / F / Alt+Enter, the goal (play, replay),
; a replay's end or the benchmark's last frame.  DS = ours, the mode set,
; bz_vinit run.  A PLAY records its key bytes into bz_rlog (SPEC.md
; 128.11.12.1) and closes the log on every way out; a REPLAY steps through it.
; -----------------------------------------------------------------------------
bz_play:
    call bz_drain               ; what the launching key typed is not a command
    call bz_pinit               ; the ball at the course's start (bzphys.inc)
    push ds
    pop es
    xor ax, ax
    mov [bz_vx], ax
    mov [bz_vy], ax
    mov [bz_tos], ax
    mov [bz_subs], ax
    mov [bz_keys], al
    mov [bz_oldv], al
    mov [bz_meas], al
    mov [bz_fin], al            ; the face's "Finished" goes with a new play
    mov [bz_rn], al             ; the log: no current run, from its first pair
%ifdef BZ_EARLYSTEP
    mov [bz_estp], ax           ; (and bz_ersp)
    mov [bz_nearly], ax
%endif
    mov word [bz_rptr], bz_rlog + BZR_RUNS
    mov di, bz_frames
    mov cx, BZ_LIVE / 2
    rep stosw
    call bz_pread               ; the props, their lanes in the map, the wheel
    mov byte [bz_blk], 0        ; (the mode set left the card lit)
    mov word [bz_wp], 1         ; waypoint 0 is the start
    mov byte [bz_first], 1
    mov byte [bz_ckey], 0ffh    ; C must go down IN play to count (an edge)
    mov byte [bz_bkey], 0ffh    ; (and Backspace, RETURN)
    mov byte [bz_pkey], 0ffh    ; (and P, PAUSE)
    mov word [bz_ptyp], 0       ; (no typed P or Backspace from before: bz_kedge)
    xor ax, ax
    mov [bz_dtr], al            ; (D: every frame measured so far)
    mov [bz_rt], al
    mov byte [bz_tilt], BZ_TILT_KEYS ; a keyboard step's tilt byte (128.14.8.2)
    mov byte [bz_tby], BZ_TILT_KEYS ; (B's steps never store it: bzphys .auto)
    mov byte [bz_tanc], 1       ; the mouse's anchor at the first frame
    mov al, [bz_mode]
    test al, 1                  ; a benchmark (B, D) replaces the last one's
    jz .nb                      ; results; B leaves the log alone
    mov byte [bz_res], 0
.nb:
    cmp al, 1
    jb .rec
    je .play
    mov ax, [bz_rlog + BZR_NRUN] ; a replay (R, D): the log's runs, none read
    mov [bz_rruns], ax          ; yet, two bytes a run or three with TILT
    call bz_rwid
    jmp short .play
.rec:                           ; a play: a new log, `BZR1`, its course and
    mov word [bz_rlog], 'BZ'    ; ball, no flags, steps or runs
    mov word [bz_rlog + 2], 'R1'
    mov al, [bz_crs]
    mov ah, [bz_mat]
    mov [bz_rlog + BZR_CRS], ax
    xor ax, ax
    mov di, bz_rlog + BZR_FLAGS
    mov cx, (BZR_RUNS - BZR_FLAGS) / 2
    rep stosw
    mov [bz_rk], al
    mov [bz_rtr], al
    cmp byte [bz_ctl], 0        ; T MOUSE: a TILT log, runs of three bytes
    je .kb                      ; (SPEC.md 128.14.8.3), and the extent the
    or byte [bz_rlog + BZR_FLAGS], BZR_TILT ; stick maps over (bz_tinit)
    call bz_tinit
.kb:
    call bz_rwid
    push es                     ; the course's identity, which a replay
    mov es, [bz_cseg]           ; compares (SPEC.md 128.12.8)
    mov di, [bz_goff]
    mov ax, [es:di + BZG_ID]
    mov [bz_rlog + BZR_ID], ax
    pop es
.play:
    call bz_clk_sample
    mov ax, [bz_subs]
    mov [bz_lsubs], ax
    mov [bz_msubs], ax
    mov ax, [bz_pitl]
    mov [bz_mpit], ax
bz_t0:
    call bz_exitchk
    jc .out
%ifdef BZ_EARLYSTEP
    cmp byte [bz_estp], 0       ; an early step ran in the last wait: this frame
    jne .on                     ; presents it before the goal or a log's end
%endif                          ; ends the run, as the frame it was due in would
    cmp byte [bz_goal], 0       ; the frame after the step whose centre is on
    je .live                    ; a GOAL cell, in play or a replay: the run is
    mov byte [bz_fin], 1        ; over (SPEC.md 128.10.6.2), and the face says
    jmp short .end              ; how long it took
.live:
    cmp byte [bz_mode], 2       ; a replay's end (R, D): the frame after its
    jb .on                      ; last recorded step (SPEC.md 128.11.12.2)
    call bz_rleft
    jnz .on
.end:
    cmp byte [bz_mode], 3       ; D ran to its end: its results stay for the
    jne .out                    ; desktop, as B's do (128.14.7.3)
    call bz_rcopy
.out:
    cmp byte [bz_mode], 0       ; a play's log closed: its last run, its
    jne .ret                    ; steps, COMPLETE
    call bz_rfin
.ret:
    ret
.on:
    test byte [bz_mode], 1      ; PAUSE (SPEC.md 128.14.4.7), in a play or a
    jnz .steps                  ; replay - B and D ignore P: P's down EDGE stops
    call bz_pkedge              ; the steps until the next one
    jz .nop
    call bz_unblank             ; (a pause right after a cut: lit, not dark)
    call bz_pause
    jc .out                     ; (Esc, F or Alt+Enter while paused)
.nop:
    cmp byte [bz_mode], 0
    jne .steps
    call bz_input               ; play: the keys, once a frame
.steps:
    cmp byte [bz_hold], 0       ; a harness's late frame on demand (SPEC.md
    je .nohold                  ; 128.12.5.6): a spin before the steps
    call bz_hspin
.nohold:
%ifdef BZ_EARLYSTEP
    xor ax, ax                  ; (a respawn in this frame's steps: the cut) -
    xchg al, [bz_ersp]          ; the early step is this frame's first, and its
    mov [bz_resp], al           ; respawn this frame's
    mov [bz_estp], ah
%else
    mov byte [bz_resp], 0       ; (a respawn in this frame's steps: the cut)
%endif
    mov cx, [bz_subs]           ; (sampled at the last frame's end mark)
    sub cx, [bz_lsubs]
    add [bz_lsubs], cx
    cmp cx, BZ_STEPS
    jbe .n
    mov cx, BZ_STEPS
.n:
%ifdef BZ_EARLYSTEP
    cmp byte [bz_goal], 0       ; the early step was the GOAL step: the last
    jne .camera
%endif
    jcxz .camera
.step:
    cmp byte [bz_mode], 2       ; a replay (R, D) steps while its log lasts
    jb .stp
    call bz_rleft
    jz .camera
.stp:
    call bz_step
    cmp byte [bz_goal], 0       ; the GOAL step is a play's last: a replay of
    jne .camera                 ; its log ends on the same step (128.11.12.2)
    loop .step
.camera:
    call bzs_frame              ; the sound: events, sub-ticks, output (128.20)
    mov al, [bz_tube]           ; the frame's HIDDEN ball, the display's: in
    or al, [bz_hid]             ; a tube, or holed out (SPEC.md 128.14.4.3:
    mov [bz_hidn], al           ; its capture frame restores its footprint)
    call bz_foot                ; RULE 0 (SPEC.md 128.12.4.4): the ball's screen
    call bz_props               ; state and new footprints, the props' walk
    call bz_camera              ; (the contact and bz_heavy), then the camera
    cmp byte [bz_full], 0       ; a full write draws every lane from the map:
    je bz_ts                    ; all of them brought to their true poses, and
    call bz_lfull               ; the slab by its box after it (bzwheel.inc)
    call bz_pfull
bz_ts:
    mov bx, 0 * 4
    call bz_mark
    call bz_mkboxes
    mov si, bz_boxes
    mov cx, [bz_nbox]
    jcxz bz_tr
.comp:
    call bz_boxc                ; the course, the shadow, the sprite
    add si, BZ_BOXD
    loop .comp
    call bz_occ                 ; ...and the occluders: ONE walk a frame, laid
    call bz_pover               ; into every box (SPEC.md 128.11.10.2); then the
bz_tr:                          ; slab when it is OVER the ball (128.12.4.5)
    mov bx, 1 * 4
    call bz_mark
    cmp byte [bz_full], 0
    jne bz_tw
    call bz_rows
bz_tw:
    mov bx, 2 * 4               ; the rows' part ends here (SPEC.md 128.12.5.6) -
    mov byte [bz_wld], 0        ; or, with no candidate, runs on to bz_tv's
    cmp byte [bz_wcn], 0        ; mark: no wheel and no mark of its own (a
    je bz_tv                    ; benchmark's mark is 1.0k clk, MEASURED)
    call bz_mark
    call bz_wheel               ; RULE 1a: the wheel, in the wait's time
    mov bx, BZ_PWHEEL * 4       ; (the wheel's part: appended, so the wave-2
bz_tv:                          ; parts keep their numbers)
    call bz_mark
%ifdef BZ_EARLYSTEP
    call bz_early               ; a due step, in the wait's time (after the wheel)
%endif
    mov byte [bz_wvok], 0       ; (no rise to reckon from: bz_vr sets it)
    pushf                       ; IF, for the row-0 box's critical section:
    cmp byte [bz_full], 0       ; bz_vr may shut interrupts at the rise, and
    jne bz_tf                   ; bz_tb's POPF opens them after the FIRST box
    call bz_r0pend
    call bz_vr
bz_tf:
    mov bx, 3 * 4
    call bz_mark
    cmp byte [bz_full], 0       ; S = (W*R0 + c0) mod 4096, KEPT (SPEC.md
    jne .whole                  ; 128.9 item 4): a step adds W a row and the
    mov ax, [bz_S]              ; column step to the shown S, the row's W*dr
    add ax, [bz_dc]             ; out of a five-entry table (dr = -2 .. 2)
    mov bx, [bz_dr]
    shl bx, 1
    add ax, [bz_wtab + 4 + bx]
    jmp short .S
.whole:
    mov ax, [bz_R0n]            ; a full write: W*R0 = rb*R0 / 2
    call bz_rbR
    shr ax, 1
    add ax, [bz_c0n]
.S:
    and ax, 0fffh
    call bz_flip
    mov [bz_S], ax
    mov ax, [bz_R0n]
    mov [bz_R0], ax
    mov ax, [bz_c0n]
    mov [bz_c0], ax
    mov ax, [bz_H]              ; no entering column: nothing left for after
    mov [bz_cdone], ax          ; the boxes
    mov byte [bz_row0], 0       ; ...and no first box at row 0 to time
    cmp byte [bz_full], 0
    je .col
    call bz_fullw
    call bz_wcalib              ; the launch's first: the wheel's calibration
    jmp short bz_tb
.col:
    cmp byte [bz_blk], 0        ; the frame after a full write: lit in this
    je .lit                     ; retrace, so its first field is whole
    call bz_unblank             ; (SPEC.md 128.14.5.6)
.lit:
    mov ax, [bz_dc]
    or ax, ax
    jz bz_tb
    mov ax, [bz_c0n]            ; moving left: the column at the left edge
    js .left                    ; (MOV keeps OR's sign)
    add ax, [bz_W]              ; moving right: the right edge's
    dec ax
.left:
    inc word [bz_ncol]
    mov [bz_ccol], ax
    mov word [bz_cdone], 0
    call bz_csplit              ; CX = the column's rows that go BEFORE the
    jcxz bz_tb                  ; first box (bz_csp the rest of the splits)
    mov [bz_cdone], cx
    mov ax, [bz_ccol]           ; (bz_csplit spent AX)
    xor bx, bx                  ; from the window's top row
    call bz_col
bz_tb:
    mov bx, 4 * 4
    call bz_mark
    mov bx, 5 * 4               ; (the part the next mark closes: the box write)
    mov si, bz_boxes            ; THE BOXES, in the order of their first lines,
    xor di, di                  ; each after the column's rows that end above
    mov cx, [bz_nbox]           ; it (SPEC.md 128.11.10.3); DI = 2 x the index
    jcxz .first
    call bz_wbox                ; the first (its column rows went before bz_tb)
.first:
    popf                        ; (bz_tv's PUSHF: interrupts as they were, from
    dec cx                      ; the end of the FIRST box)
    jle .rest
.box:
    add si, BZ_BOXD
    inc di
    inc di
    mov ax, [bz_csp + di]
    cmp ax, [bz_cdone]
    jbe .bw
    call bz_tcmid
.bw:
    call bz_wbox
    loop .box
.rest:
    mov cx, [bz_H]              ; the column's rows under the last box
    sub cx, [bz_cdone]
    jbe bz_tc.lead
bz_tc:
    call bz_mark                ; BX = 5*4: the box write ends here
    mov ax, [bz_ccol]
    mov bx, [bz_cdone]
    call bz_col
    mov bx, 4 * 4               ; ...which are the flip+columns part's
.lead:
    call bz_lead                ; RULE 5 (bzwheel.inc): busy, the box write's
bz_presented:
    call bz_mark
    cmp byte [bz_disc], 0       ; a CENTRED full write (the first frame, a
    je .kept                    ; cut): its elapsed sub-ticks are DISCARDED,
    mov byte [bz_disc], 0       ; so the ball just put at rest is not caught up
    mov ax, [bz_subs]           ; with 8 steps (SPEC.md 128.10.8 item 3)
    mov [bz_lsubs], ax
.kept:
    inc word [bz_frames]        ; SATURATING (a D past 65,535 frames shows the
    jnz .fsat                   ; cap, never a wrapped plausible count:
    dec word [bz_frames]        ; 128.14.22 item 13)
.fsat:
    test byte [bz_mode], 1      ; a benchmark's frame (a play and a replay
    jz .fper                    ; measure nothing): this mark is the next
    mov ax, [bz_mpit]           ; frame's base, and a MEASURED frame's period
    mov cx, [bz_msubs]          ; is this mark less the last frame's - what the
    xchg ax, [bz_ppit]          ; marks' gaps summed to (the frame before a
    xchg cx, [bz_psubs]         ; measured one is a benchmark's too: the first
    cmp byte [bz_meas], 0       ; frame is a full write, never measured)
    je .fper
    inc word [bz_mfr]
    sub ax, [bz_ppit]           ; the phase moved (signed) ...
    cwd
    sub cx, [bz_psubs]
    neg cx                      ; ...+ the whole sub-ticks
    jcxz .per
.sub:
    add ax, BZ_SUB
    adc dx, 0
    loop .sub
.per:                           ; DX:AX = the period, PIT counts: the worst...
    cmp dx, [bz_fmax + 2]
    jb .notmax
    ja .max
    cmp ax, [bz_fmax]
    jbe .notmax
.max:
    mov [bz_fmax], ax
    mov [bz_fmax + 2], dx
.notmax:
    or dx, dx                   ; ...and a MISSED refresh: a period over 1.5
    jnz .miss                   ; refreshes means the retrace it was paced by
    cmp ax, [bz_mlim]           ; came round again before the frame was done
    jbe .fper
.miss:
    inc word [bz_miss]
.fper:
    push ds                     ; the footprints drawn are the next frame's old
    pop es                      ; ones: the ball's and the shadow's rects, and
    mov si, bz_nfx0             ; whether the shadow was drawn
    mov di, bz_ofx0
    mov cx, 8
    rep movsw
    mov al, [bz_snv]
    mov [bz_sov], al
    xor al, al                  ; (a HIDDEN ball, in a tube or holed, left
    cmp [bz_hidn], al           ; nothing of itself on the card to restore:
    jne .ov                     ; SPEC.md 128.12.6.1, 128.14.4.3)
    inc ax
.ov:
    mov [bz_oldv], al
    cmp byte [bz_mode], 1
    jne .next
    cmp word [bz_frames], BZ_BENCH
    jae bz_rcopy                ; the benchmark is done
.next:
    jmp bz_t0

%ifdef BZ_EARLYSTEP
; -----------------------------------------------------------------------------
; bz_early - THE EARLY STEP, at bz_tv: the wheel is done and the frame would
; now idle until the retrace.  If a step is ALREADY DUE by the loop's own rule
; (a sub-tick sampled past bz_lsubs: never a predicted one) and the wait holds
; BZ_EROOM counts still, it runs here and bz_lsubs takes it, so the next
; frame's top has one fewer to run: the same steps in the same order with the
; same key bytes off the log, only earlier.  A play's early step reads the keys
; last sampled (bz_keys, bz_tilt: this frame's bz_input), where it would have
; read the next frame's.
;   The room is reckoned as the wheel reckons (bz_wnow: the counts since the
; last wait's sample S, the refresh bz_wrefp): the next rise is at S + refp, or
; S + 2 refp on a frame already more than BZ_ESYNC past its first sync - the
; long wait of a frame that missed, where a step most wants running.  No step
; when the last wait gave no sample (bz_wvok: a time-out, a full write), on a
; full write (no wait), when the wheel marked a lane for the LEAD (bz_wld: the
; one thing after the wait that could commit a lane; with none, nothing drawn
; or keyed after here reads the ball - the boxes are composed, the column is
; the map's, bz_presented copies bz_foot's footprints), after the GOAL step,
; or when a replay's log is spent.
;   This frame shows the state BEFORE the step.  What the step leaves for the
; frame level is carried to the next frame, where it was due: bz_estp makes
; bz_t0 present that frame before the goal or the log's end stops the run,
; and a respawn's bz_resp is held in bz_ersp over this frame's.
; Preserves nothing.
; -----------------------------------------------------------------------------
bz_early:
    mov ax, [bz_subs]
    cmp ax, [bz_lsubs]
    je .no                      ; none due
    mov al, [bz_full]
    or al, [bz_goal]
    or al, [bz_wld]
    or al, [bz_noearly]         ; (a harness's poke)
    jnz .no
    cmp [bz_wvok], al
    je .no
    cmp byte [bz_mode], 2
    jb .room
    call bz_rleft
    jz .no
.room:
    call bz_wnow                ; AX = the counts since S (CF: past a word)
    jc .no
    mov dx, [bz_wrefp]
    sub ax, dx
    jb .left                    ; before the first sync
    cmp ax, BZ_ESYNC            ; just past it: bz_vr may still take it
    jb .no
    sub ax, dx
    jae .no                     ; past the second: no reckoning that far
.left:
    neg ax                      ; AX = the counts to the next rise
    cmp ax, BZ_EROOM
    jb .no
    xor al, al
    xchg al, [bz_resp]
    push ax
    call bz_step
    pop ax
    xchg al, [bz_resp]
    mov [bz_ersp], al
    mov byte [bz_estp], 1
    inc word [bz_lsubs]
    inc word [bz_nearly]
.no:
    ret
%endif

; a benchmark's end (B's last frame, D's log spent): the instruments' results
; stay for the desktop's RESULTS page.  ES = ours.  Clobbers CX, SI, DI.
bz_rcopy:
    push ds
    pop es
    mov si, bz_frames
    mov di, bz_rframes
    mov cx, BZ_LIVE / 2
    rep movsw
    mov byte [bz_res], 1
    ret

; bz_tcmid - the entering column's rows [bz_cdone, AX) that end above the next
; box (SPEC.md 128.11.10.3), written between two boxes.  NO MARK: they are
; billed to the box write's part, so the flip+columns part is the column rows
; before the first box and after the last, and a frame's mark count does not
; grow with its boxes (a mark is ~1.0k of its own on a measured frame, ~0.4k
; in play).  Preserves all but the flags.
bz_tcmid:
    push ax
    push bx
    push cx
    mov cx, ax
    mov bx, [bz_cdone]
    sub cx, bx
    mov [bz_cdone], ax
    mov ax, [bz_ccol]
    call bz_col
    pop cx
    pop bx
    pop ax
    ret

; bz_wbox - box SI (index DI / 2) to the card, and on a TIMED frame against
; the beam (bz_latechk, SPEC.md 128.11.10.3): late if not STARTED before the
; beam reached its first window line - line 0 for a first box at window row 0,
; whose column rows went first - or not DONE before it reached its last (a
; writer at a steady speed is ahead of the beam at every line between if it is
; at both ends).  A late box is counted in bz_late, and finished.  TIMED is
; where something reads the verdict: a benchmark's measured frame (bz_meas,
; never a full write), or a frame a harness asked for with bz_tpoke (the ring
; probe's, in play; a full write's boxes are still not timed).  A play or a
; replay times nothing: the pair is ~1.65k clocks a box.  Preserves all but
; AX, DX and the flags.
bz_wbox:
    xor dx, dx                  ; DL: late at its start or its end; DH: timed
    cmp byte [bz_meas], 0       ; a benchmark's measured frame...
    jne .t
    cmp byte [bz_tpoke], 0      ; ...or a harness's poke (bz_meas is 0 on a
    je .wr                      ; full write, and so is this, below)
    cmp byte [bz_full], 0       ; (a full write's boxes follow it: not timed)
    jne .wr
.t:
    inc dh
    mov ax, [si + 2]
    sub ax, [bz_wtop]
    or di, di
    jnz .ls
    cmp byte [bz_row0], 0
    je .ls
    xor ax, ax
.ls:
    call bz_latechk
    adc dl, 0
.wr:
    call bz_boxw
    or dh, dh
    jz .out
    mov ax, [si + 2]
    add ax, [si + 6]
    dec ax
    sub ax, [bz_wtop]
    call bz_latechk
    adc dl, 0
    jz .out
    inc word [bz_late]
.out:
    ret

; -----------------------------------------------------------------------------
; THE REPLAY LOG (SPEC.md 128.11.12): the recorder's slow paths and the player.
; bz_step's step 1 records a play's key byte inline while it extends the
; current run, and calls bz_rrec when it does not.
; -----------------------------------------------------------------------------
; bz_rrec - BL = this step's key byte and BH its tilt byte, which do not
; extend the current run (another byte, or the run at 255): the run is FLUSHED
; and BL, BH start the next - unless the buffer is then full, when the log is
; TRUNCATED: flags bit 1, the steps so far kept in bz_rtrs, and nothing more
; recorded (bz_rk = FFh, a byte no step has, sends every later step here,
; where bz_rtr stops it).  A keyboard log's runs are pairs and a TILT log's
; triples (bz_rw), and both fill bz_rlog exactly.  Clobbers AX, DX, DI.
bz_rrec:
    cmp byte [bz_rtr], 0
    jne .out
    call bz_rstore
    cmp word [bz_rptr], bz_rlog + BZR_SIZE
    jb .new
    mov byte [bz_rtr], 1        ; full: TRUNCATED at this step
    or byte [bz_rlog + BZR_FLAGS], BZR_TRUNC
    mov byte [bz_rk], 0ffh
    mov ax, [bz_nstep]
    mov dx, [bz_nstep + 2]
    mov [bz_rtrs], ax
    mov [bz_rtrs + 2], dx
    ret
.new:
    mov [bz_rk], bl
    mov [bz_rt], bh
    mov byte [bz_rn], 1
.out:
    ret

; bz_rstore - the current run (bz_rk, [bz_rt,] bz_rn), if it has a step,
; stored at bz_rptr as a pair, or a triple in a TILT log, and counted.
; Clobbers AX, DI.
bz_rstore:
    mov ah, [bz_rn]
    or ah, ah
    jz .out
    mov al, [bz_rk]
    mov di, [bz_rptr]
    cmp byte [bz_rw], 2
    je .pair
    mov [di], al                ; (key byte, tilt byte, count)
    inc di
    mov al, [bz_rt]
.pair:
    mov [di], ax
    inc di
    inc di
    mov [bz_rptr], di
    inc word [bz_rlog + BZR_NRUN]
    mov byte [bz_rn], 0
.out:
    ret

; bz_rwid - [bz_rw] = the held log's run width: 3 with TILT, else 2.
; Preserves all but the flags.
bz_rwid:
    mov byte [bz_rw], 2
    test byte [bz_rlog + BZR_FLAGS], BZR_TILT
    jz .out
    inc byte [bz_rw]
.out:
    ret

; bz_rfin - a play's end (the goal, Esc, F or Alt+Enter): the last run
; flushed, the steps written once - bz_nstep, or bz_rtrs if TRUNCATED - and
; COMPLETE set.  Clobbers AX, DX, DI.
bz_rfin:
    call bz_rstore
    mov ax, [bz_nstep]
    mov dx, [bz_nstep + 2]
    cmp byte [bz_rtr], 0
    je .w
    mov ax, [bz_rtrs]
    mov dx, [bz_rtrs + 2]
.w:
    mov [bz_rlog + BZR_STEPS], ax
    mov [bz_rlog + BZR_STEPS + 2], dx
    or byte [bz_rlog + BZR_FLAGS], BZR_DONE
    mov byte [bz_rlog + BZR_PHYS], BZ_PHYSV ; the physics it was made under
    ret                         ; (SPEC.md 128.14.7.2; +7 was zero)

; bz_rleft - a replay: ZF = 1 when the log is spent (no step left in the
; current run and no run left to read).  Clobbers AX.
bz_rleft:
    mov al, [bz_rn]
    or al, [bz_rruns]
    or al, [bz_rruns + 1]
    ret

; bz_rnext - a replay's next key byte -> BL, and its tilt byte -> [bz_tby]:
; from the current run, or the next pair (triple, in a TILT log) once it is
; spent.  The log is the package's own - written by bz_rrec, or a file that
; passed L's checks, or a part the tool checked: trusted, and decoded without
; a check (SPEC.md 128.11.12.2, 128.14.7.2).  bz_play's step loop asks
; bz_rleft first.  Clobbers AX, SI.
bz_rnext:
    cmp byte [bz_rn], 0
    jne .cur
    mov si, [bz_rptr]
    lodsb                       ; the key byte
    mov [bz_rk], al
    mov al, BZ_TILT_KEYS        ; a keyboard log's caps are 8 (128.14.8.2)
    cmp byte [bz_rw], 2
    je .k
    lodsb                       ; a TILT log's tilt byte
.k:
    mov [bz_rt], al
    lodsb                       ; the count (1 - 255)
    mov [bz_rn], al
    mov [bz_rptr], si
    dec word [bz_rruns]
.cur:
    dec byte [bz_rn]
    mov al, [bz_rt]
    mov [bz_tby], al
    mov bl, [bz_rk]
    ret

; -----------------------------------------------------------------------------
; the keys.  bz_exitchk: CF = 1 leave (Alt+Enter, Esc, F); every typed key is
; drained so none leaks to the desktop (WireBall's rule).  Clobbers AX.
; -----------------------------------------------------------------------------
bz_exitchk:
    call os88alt_edge
    jc .leave
    push di                     ; THE FRAME'S KEYS, ONE CALL (SPEC.md 9.7.3):
    mov di, bz_kmap             ; Esc here, bz_input's six and bz_kedge's held
    call OSAPI_KEY_MAP          ; key are each one test of this copy, where
    pop di                      ; OSAPI_KEY_DOWN was a far call a key
    KEYMAP_TEST bz_kmap, KSC_ESC
    jnz .leave
.drain:
    mov ah, 1
    int 16h
    jz .stay
    xor ah, ah
    int 16h
    cmp al, 27
    je .leave
    cmp ah, BZ_KSC_P            ; P and Backspace TYPED: their presses, for
    jne .bk                     ; bz_kedge (a byte, not an OSAPI_KEY_DOWN a
    mov byte [bz_ptyp], 1       ; frame: SPEC.md 128.14.12)
.bk:
    cmp ah, BZ_KSC_BKSP
    jne .f
    mov byte [bz_btyp], 1
.f:
    or al, 20h
    cmp al, 'f'
    je .leave
    jmp .drain
.stay:
    clc
    ret
.leave:
    stc
    ret

; P's down EDGE (SPEC.md 128.14.4.7): ZF = 0 for a press.  Clobbers AX, SI, DI.
bz_pkedge:
    mov al, BZ_KSC_P
    mov si, bz_ptyp
    mov di, bz_pkey
; bz_kedge - a key's down EDGE off the TYPED keys: AL = its make code, SI = its
; typed byte (bz_exitchk sets it when the BIOS buffer gives the key), DI = its
; HELD byte.  A press is a typed key while the key is not held; it sets HELD,
; and while HELD the key is asked (OSAPI_KEY_DOWN) once a call until it is up,
; so a typematic repeat is never a second press - and a key that is up costs
; two byte tests, not an API call (SPEC.md 128.14.12).  bz_play seeds HELD FFh
; and clears typed, so the key must go down IN play to count.  ZF = 0: a
; press.  Clobbers AX.
bz_kedge:
    cmp byte [di], 0
    jne .held
    xor ah, ah
    xchg ah, [si]
    or ah, ah                   ; (ZF = 1: none)
    jz .out
    mov byte [di], 0ffh         ; (ZF = 0 still: a press)
.out:
    ret
.held:
    push bx                     ; held still?  bz_exitchk's map, this frame's
    push cx                     ; (every caller runs after it)
    mov bl, al
    mov cl, 3
    shr bl, cl
    xor bh, bh
    mov cl, al
    and cl, 7
    mov al, 1
    shl al, cl
    and al, [bz_kmap + bx]
    pop cx
    pop bx
    neg al
    sbb al, al                  ; FFh held, 0 up
    mov [di], al                ; up: the next typed key is a press
    xor al, al                  ; (ZF = 1; a typed key while held - a repeat -
    mov [si], al                ; is dropped)
    ret

; bz_pause - PAUSED (SPEC.md 128.14.4.7): no step runs and nothing new is
; presented - the last frame stays on the glass - while the keys are read,
; until P's next down edge (CF = 0) or Esc, F or Alt+Enter (CF = 1, leave).
; The sound keeps its own time (bzs_frame: the events are the counters', and
; no step moves them), the clock is sampled so no reload is missed, and on
; the way out the sub-ticks the pause took are DISCARDED, as at a cut
; (128.10.6.2): a pause adds no steps, so a play's log - steps - is the one
; it would have been, and the course's time stands still.  Clobbers AX, SI,
; DI.
bz_pause:
    call bz_clk_sample
    call bzs_frame
    call bz_exitchk
    jc .out
    call bz_pkedge
    jz bz_pause
    mov ax, [bz_subs]
    mov [bz_lsubs], ax
    clc
.out:
    ret

; every typed key, discarded.  Clobbers AX.
bz_drain:
    mov ah, 1
    int 16h
    jz .out
    xor ah, ah
    int 16h
    jmp bz_drain
.out:
    ret

; the step's KEY BYTE -> [bz_keys] (SPEC.md 128.11.7.2): the arrows, Space
; (bit 4, the Hop) and Left Shift (bit 5, Grip) held - and C's key-down EDGE
; (not its repeat) cycles the camera mode (SPEC.md 128.9).  Left Shift is the
; BIOS's shift flags (int 16h AH = 02h, bit 1), NOT SPEC.md 9.7's map, which
; takes a 101-key keyboard's fake shifts (E0 2A before a grey arrow) as Left
; Shift held.  Preserves all but the flags.
bz_input:
    push ax
    push bx
    xor bl, bl                  ; (bz_exitchk filled bz_kmap this frame)
    KEYMAP_TEST bz_kmap, BZ_KSC_C
    jz .cup
    dec bl                      ; BL = FFh while C is down
.cup:
    mov al, bl
    xchg al, [bz_ckey]          ; AL = last frame's
    not al
    and al, bl                  ; down now and not then: the edge
    jz .bksp
    call bz_cnext
.bksp:
    xor bl, bl                  ; Backspace, RETURN (SPEC.md 128.14.4.5): its
    push si                     ; down EDGE (bz_kedge, the typed key) puts bit
    push di                     ; 6 in the frame's key byte, and the first step
    mov al, BZ_KSC_BKSP         ; that reads it clears it (bzphys.inc .kret) -
    mov si, bz_btyp             ; one press, one step's bit however long it is
    mov di, bz_bkey             ; held
    call bz_kedge
    pop di
    pop si
    jz .arrows
    mov bl, BZ_K_RET
.arrows:
    KEYMAP_TEST bz_kmap, KSC_LEFT
    jz .r
    or bl, BZ_K_L
.r:
    KEYMAP_TEST bz_kmap, KSC_RIGHT
    jz .u
    or bl, BZ_K_R
.u:
    KEYMAP_TEST bz_kmap, KSC_UP
    jz .d
    or bl, BZ_K_U
.d:
    KEYMAP_TEST bz_kmap, KSC_DOWN
    jz .sp
    or bl, BZ_K_D
.sp:
    KEYMAP_TEST bz_kmap, KSC_SPACE
    jz .sh
    or bl, BZ_K_HOP
.sh:
    mov ah, 2                   ; the BIOS's shift flags: bit 1 Left Shift
    int 16h
    test al, 2
    jz .ms
    or bl, BZ_K_GRIP
.ms:
    cmp byte [bz_ctl], 0        ; T MOUSE: the stick, merged (128.14.8)
    je .out
    call bz_tmouse
.out:
    mov al, [bz_keys]           ; RETURN's bit is LATCHED: it stays until a step
    and al, BZ_K_RET            ; reads it (bzphys.inc .kret clears it), so a
    or bl, al                   ; press on a frame that runs no step is not lost
    mov [bz_keys], bl
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; THE MOUSE AS A TILT STICK (SPEC.md 128.14.8.1), a play's under T MOUSE.  Per
; screen axis of extent E (the BRACKET's display, OSAPI_VIDEO read inside it):
; FULL = E / 4 and DZ = FULL / 4, and the pointer's offset d from the ANCHOR
; sets the arrow's direction and its force level's CAP 0 - 8:
;   cap(d) = 0 for |d| <= DZ, else min(8, ceil(8 (|d| - DZ) / (FULL - DZ)))
; which is the count of the eight boundaries T[c] = DZ + floor(c R / 8), c 0 -
; 7, R = FULL - DZ, that |d| is past - built ONCE a play (bz_tinit: shifts,
; no divide), so a frame compares.  A cap moves only when |d| is more than H =
; R / 32 past the boundary it crosses (hysteresis), so a steady hand makes
; long runs.  The anchor is the pointer at the play's first frame and at every
; respawn (a fall, a shatter, RETURN: the ball is still), clamped inward so a
; full tilt fits each way; the stick is dead until both caps have once been 0
; (the pointer inside the dead zone round the anchor - the cursor is not drawn
; in the bracket, and the ball not rolling is the cue).  The left button is
; Hop and the right Grip; an arrow KEY held on an axis wins that axis, cap 8.
; bbcourse.TiltStick is the model.
; -----------------------------------------------------------------------------
BZT_ANC     equ 0               ; an axis: the anchor
BZT_LO      equ 2               ; ...its clamp, FULL and E - 1 - FULL
BZT_HI      equ 4
BZT_H       equ 6               ; ...the hysteresis, R / 32
BZT_CAP     equ 8               ; ...byte: the cap now, 0 - 8
BZT_NEG     equ 9               ; ...byte: FFh while d < 0
BZT_T       equ 10              ; ...T[0] - T[7]
BZT_SIZE    equ 26

; bz_tinit - the extent read and both axes' tables built: once a play, in the
; bracket after the mode set.  Clobbers AX, BX, CX, DX, SI, DI.
bz_tinit:
    push es
    call OSAPI_VIDEO            ; AX = the width, BX = the height (the bracket's
    pop es                      ; display alone, SPEC.md 39.18.3)
    mov di, bz_tax
    call .axis
    xchg ax, bx
    mov di, bz_tay
.axis:                          ; AX = E -> the axis at DI
    push bp
    mov cx, ax
    shr ax, 1
    shr ax, 1                   ; AX = FULL
    mov [di + BZT_LO], ax
    sub cx, ax
    dec cx
    mov [di + BZT_HI], cx
    mov cx, ax
    shr cx, 1
    shr cx, 1                   ; CX = DZ
    sub ax, cx                  ; AX = R
    mov dx, ax
    shr dx, 1
    shr dx, 1
    shr dx, 1
    shr dx, 1
    shr dx, 1
    mov [di + BZT_H], dx
    lea si, [di + BZT_T]
    xor dx, dx                  ; c R
    mov bp, BZ_LVLMAX
.t:
    push dx
    shr dx, 1
    shr dx, 1
    shr dx, 1
    add dx, cx
    mov [si], dx
    pop dx
    inc si
    inc si
    add dx, ax
    dec bp
    jnz .t
    pop bp
    ret

; bz_tmouse - BL = the keyboard's key byte -> BL with the stick's arrows and
; buttons, [bz_tilt] = its caps (x << 4 | y).  Preserves all but BL and the
; flags.
bz_tmouse:
    push ax
    push cx
    push dx
    push si
    push di
    push es
    call OSAPI_MOUSE            ; CX = x, DX = y, AL = the buttons
    pop es
    test al, 1
    jz .nl
    or bl, BZ_K_HOP
.nl:
    test al, 2
    jz .nr
    or bl, BZ_K_GRIP
.nr:
    mov al, [bz_tanc]           ; the first frame, or a respawn's: anchored
    or al, [bz_resp]            ; here, and dead until the dead zone
    jz .run
    mov byte [bz_tanc], 0
    mov byte [bz_tarm], 0
    mov ax, cx
    mov di, bz_tax
    call .anchor
    mov ax, dx
    mov di, bz_tay
    call .anchor
.run:
    push dx
    mov ax, cx
    mov di, bz_tax
    call .cap
    pop ax
    mov di, bz_tay
    call .cap
    mov ax, [bz_tax + BZT_CAP - 1] ; AH = the x cap ...
    mov al, [bz_tay + BZT_CAP]  ; ...AL the y cap
    or ax, ax
    jnz .armed
    mov byte [bz_tarm], 1       ; both 0: inside the dead zone
.armed:
    cmp byte [bz_tarm], 0
    jne .x
    xor ax, ax                  ; not yet: no tilt
.x:
    mov dx, (BZ_K_L | BZ_K_R) | (BZ_K_R << 8)
    mov si, bz_tax
    xchg al, ah                 ; AL = the x cap
    call .merge
    xchg al, ah                 ; AH = the x cap, AL = the y cap
    mov dx, (BZ_K_U | BZ_K_D) | (BZ_K_D << 8)
    mov si, bz_tay
    call .merge
    shl ah, 1
    shl ah, 1
    shl ah, 1
    shl ah, 1
    or al, ah
    mov [bz_tilt], al
    pop di
    pop si
    pop dx
    pop cx
    pop ax
    ret
; AL = an axis's cap, SI the axis, DL its two arrows, DH its positive one:
; a key held on the axis wins it (cap 8); else the stick's arrow when its cap
; is not 0
.merge:
    test bl, dl
    jz .m
    mov al, BZ_LVLMAX
    ret
.m:
    or al, al
    jz .mo
    xor dl, dh                  ; DL = the negative arrow
    cmp byte [si + BZT_NEG], 0
    jne .mn
    mov dl, dh
.mn:
    or bl, dl
.mo:
    ret
; AX = the pointer -> the axis at DI anchored there, clamped inward; cap 0
.anchor:
    cmp ax, [di + BZT_LO]
    jae .al
    mov ax, [di + BZT_LO]
.al:
    cmp ax, [di + BZT_HI]
    jbe .ah
    mov ax, [di + BZT_HI]
.ah:
    mov [di + BZT_ANC], ax
    mov byte [di + BZT_CAP], 0
    ret
; AX = the pointer -> the axis at DI: its cap moved past the boundaries |d|
; is more than H beyond (up from T[cap], down from T[cap - 1]), its sign kept.
; Clobbers AX, CX, DX, SI.
.cap:
    sub ax, [di + BZT_ANC]
    cwd
    mov [di + BZT_NEG], dl
    xor ax, dx
    sub ax, dx                  ; AX = |d|
    mov dx, ax
    sub ax, [di + BZT_H]        ; AX = |d| - H, DX = |d| + H: once an axis,
    add dx, [di + BZT_H]        ; not once a boundary (128.14.12)
    mov cl, [di + BZT_CAP]
    xor ch, ch
    mov si, cx
    shl si, 1
    add si, di                  ; [si + BZT_T] = T[cap]
.up:
    cmp cl, BZ_LVLMAX
    jae .dn
    cmp ax, [si + BZT_T]        ; |d| - H > T[cap]: up one
    jle .dn
    inc cx
    inc si
    inc si
    jmp .up
.dn:
    jcxz .cd
    cmp dx, [si + BZT_T - 2]    ; |d| + H <= T[cap - 1]: down one
    jg .cd
    dec cx
    dec si
    dec si
    jmp .dn
.cd:
    mov [di + BZT_CAP], cl
    ret

; the next camera mode, GLIDE -> TRICKLE -> GLIDE.  Preserves all
; but the flags.  The camera picks its new state up itself (bz_camera's tail).
bz_cnext:
    inc byte [bz_cmode]
    cmp byte [bz_cmode], BZ_CMODES
    jb .out
    mov byte [bz_cmode], 0
.out:
    ret

; -----------------------------------------------------------------------------
; bz_auto - THE AUTOPILOT (SPEC.md 128.6): the keys it would hold toward the
; next waypoint of the course's route (the course part's, 128.10.5.2: on BENCH
; down the descent, a loop round the landing, the traverse, toward the climb,
; 128.10.11.1).  It wants a velocity of 8/256 px a
; step per px of distance, at most BZ_VMAX, and presses the arrow that closes
; the gap.  Deterministic from the first frame.  Out: BL.  Preserves all else.
; -----------------------------------------------------------------------------
bz_auto:
    push ax
    push cx
    push dx
    push si
    push es
    mov es, [bz_cseg]           ; the route is the course part's (128.10.5.2)
.again:
    mov si, [bz_wp]
    shl si, 1
    shl si, 1
    add si, [bz_wayoff]
    mov ax, [es:si]
    sub ax, [bz_bx + 1]         ; AX = dx, px
    mov cx, [es:si + 2]
    sub cx, [bz_by + 1]         ; CX = dy
    mov dx, [bz_wp]
    inc dx
    cmp dx, [bz_nway]
    jae .steer                  ; the last one is held
    mov dx, ax
    call bz_abs
    cmp dx, BZ_REACH
    jae .steer
    mov dx, cx
    call bz_abs
    cmp dx, BZ_REACH
    jae .steer
    inc word [bz_wp]            ; reached: the next
    jmp .again
.steer:
    xor bl, bl
    call bz_want                ; AX = the velocity wanted in x
    sub ax, [bz_vx]
    cmp ax, BZ_ACC / 2
    jle .notr
    or bl, BZ_K_R
    jmp .y
.notr:
    cmp ax, -(BZ_ACC / 2)
    jge .y
    or bl, BZ_K_L
.y:
    mov ax, cx
    call bz_want
    sub ax, [bz_vy]
    cmp ax, BZ_ACC / 2
    jle .notd
    or bl, BZ_K_D
    jmp .out
.notd:
    cmp ax, -(BZ_ACC / 2)
    jge .out
    or bl, BZ_K_U
.out:
    pop es
    pop si
    pop dx
    pop cx
    pop ax
    ret

; DX -> |DX|
bz_abs:
    or dx, dx
    jns .out
    neg dx
.out:
    ret

; AX = a distance, px (|AX| < 4096) -> AX = 8 x it, clamped to +-BZ_VMAX
bz_want:
    shl ax, 1
    shl ax, 1
    shl ax, 1
    cmp ax, BZ_VMAX
    jle .lo
    mov ax, BZ_VMAX
.lo:
    cmp ax, -BZ_VMAX
    jge .out
    mov ax, -BZ_VMAX
.out:
    ret

; -----------------------------------------------------------------------------
; bz_foot - RULE 0's first half (SPEC.md 128.12.4.4), once a frame after the
; steps: the ball's cell row s_b (the idle test's and the occluders',
; 128.10.8), its integer px and py, its sprite and shadow (bz_sprite), and its
; NEW FOOTPRINTS as rects (bz_nfx0, and bz_snx0 the shadow's: the ball's
; columns, lines spy .. spy + 5) - which depend on the picture, not on the
; window, so bz_props reads them before the camera and bz_mkboxes after it,
; computed once.  Clobbers AX, BX, CX, DX.
; -----------------------------------------------------------------------------
bz_foot:
    mov ax, [bz_gx + 1]
    mov dx, [bz_gy + 1]
    mov cl, 4
    shr ax, cl
    shr dx, cl
    add ax, dx
    mov [bz_sb], ax
    mov ax, [bz_bx + 1]
    mov [bz_px], ax
    mov ax, [bz_by + 1]
    mov [bz_py], ax
    call bz_sprite
    mov ax, [bz_px]             ; the new footprints: the ball's ...
    mov bx, ax
    mov cl, 3
    shr ax, cl
    mov [bz_nfx0], ax
    mov [bz_snx0], ax
    shr bx, 1
    shr bx, 1
    add bx, BZ_BAL_RB - 1
    shr bx, 1
    mov [bz_nfx1], bx
    mov [bz_snx0 + 2], bx
    mov ax, [bz_py]
    mov [bz_nfy0], ax
    add ax, BZ_BAL_ROWS - 1
    mov [bz_nfy1], ax
    mov ax, [bz_spy]            ; ...and the shadow's, the same columns
    mov [bz_snx0 + 4], ax
    add ax, BZ_BAL_SHDROWS - 1
    mov [bz_snx0 + 6], ax
    ret

; -----------------------------------------------------------------------------
; bz_camera - the new window, from the ball's position (bz_foot, rule 0).  Runs ONCE A FRAME, after the frame's steps (SPEC.md
; 128.9: the camera is part of the simulation, and its cadence is the frame
; rate's).  The first frame centres the window on the ball and is a FULL WRITE,
; as is any step past BZ_MAXR/BZ_MAXC.  After it, the MODE (bz_cmode; GLIDE in
; a benchmark, SPEC.md 128.11.11.1):
;
;   GLIDE   LATTICE since wave 6b (bz_lattice, SPEC.md 128.17.6.2): the
;           camera RESTS, or it PANS to a lattice framing ahead of the ball,
;           at one rate a pan that only rises; a pan never reverses inside
;           the band, and coming back needs a hysteresis more
;   TRICKLE wave 0's camera, unchanged (SPEC.md 128.5): the "classic" one
;
; Both read the camera's centre line off 128.16.7's GROUND LINE, at most
; BZ_MAXR rows and BZ_MAXC columns a frame, clamped to the course - so 128.2
; rule 4's column split is the same in both.  GLIDE's "fast" across is the
; ball's travel over the last four frames, kept in every mode (the ring
; bz_trx: SPEC.md 128.11.11.1, bbcourse.Glide's).  GLIDE's steps are DELAYED
; on a HEAVY frame (bz_lhv, from bz_props's bz_heavy and bz_pflag's near-edge
; bits, SPEC.md 128.17.6.3); TRICKLE is wave 0's exactly.  A harness's
; bz_camscr replaces GLIDE by a SCRIPT (128.17.6.7); its clearing is a cut.
; Sets bz_R0n, bz_c0n, bz_dr, bz_dc, bz_full, bz_meas, bz_cuse.  Preserves
; nothing.
; -----------------------------------------------------------------------------
bz_camera:
    mov al, [bz_cmode]          ; the mode this frame: the benchmark's is GLIDE
    cmp byte [bz_mode], 1       ; whatever the player chose, so its route and
    jne .muse                   ; its numbers stay comparable (bz_cmode is
    xor al, al                  ; left as it was)
.muse:
    xchg al, [bz_cuse]          ; GLIDE again after TRICKLE (C): LATTICE
    or al, al                   ; starts at rest, its bands at the window
    jz .ncs0                    ; as it stands
    cmp byte [bz_cuse], 0
    jne .ncs0
    call bz_latrst
.ncs0:
    cmp byte [bz_camscr], 0     ; bz_camscr CLEARED after a scripted frame
    jne .ncs                    ; (bz_scnt bit 7): a cut (128.17.6.7)
    test byte [bz_scnt], 80h
    jnz .cut
.ncs:
    cmp byte [bz_resp], 0       ; THE CUT (SPEC.md 128.10.8 item 3): a frame
    je .nocut                   ; whose steps respawned the ball where its
    call bz_outwin              ; footprint is not wholly inside the window
    jnc .nocut                  ; is the first frame's centred full write
.cut:
    mov byte [bz_first], 1
.nocut:
    mov cl, [bz_lsh]
    cmp byte [bz_first], 0
    je .modes
    ; --- the first frame (or a cut): the window centred on the ball ---
    mov byte [bz_first], 0
    mov byte [bz_disc], 1       ; (bz_presented discards its sub-ticks)
    mov ax, [bz_py]
    add ax, 8 - BZ_LINES / 2
    jge .iy
    xor ax, ax
.iy:
    shr ax, cl
    mov [bz_R0n], ax
    mov ax, [bz_W]
    shl ax, 1
    shl ax, 1                   ; half the window's px
    neg ax
    add ax, [bz_px]
    add ax, 8
    jge .ix
    xor ax, ax
.ix:
    shr ax, 1
    shr ax, 1
    shr ax, 1
    mov [bz_c0n], ax
    call bz_clampwin
    mov ax, [bz_R0n]
    mov [bz_R0], ax
    mov ax, [bz_c0n]
    mov [bz_c0], ax
    mov byte [bz_full], 1
    call bz_latrst              ; every axis at rest, the script's count 0
    xor ax, ax
    mov [bz_clat], ax           ; the ground line from the ball, unlatched
    mov ax, [bz_gz + 1]         ; (wave 6, 128.16.7)
    mov [bz_cgz], ax
    mov ax, [bz_bx]             ; the travel ring filled with the present
    mov bx, 6                   ; position: at rest
.tf:
    mov [bz_trx + bx], ax
    dec bx
    dec bx
    jns .tf
    jmp .decided
.modes:
    cmp byte [bz_camscr], 0     ; a harness's SCRIPTED camera (128.17.6.7):
    je .ring                    ; neither the ring, the ground line nor
    jmp .script                 ; LATTICE runs
.ring:
    ; --- the travel over four frames (SPEC.md 128.11.11.1): read the slot
    ; written four frames ago, then write the present into it, step the index
    mov bl, [bz_tri]
    xor bh, bh
    shl bx, 1
    mov ax, [bz_bx]
    mov dx, ax
    xchg ax, [bz_trx + bx]
    sub dx, ax
    call bz_abs
    cmp dx, BZ_GTRX + 1         ; fast across: more than BZ_GTRX
    sbb al, al
    inc ax
    mov [bz_gfast], al
    inc byte [bz_tri]
    and byte [bz_tri], 3
    ; --- THE GROUND LINE (wave 6, SPEC.md 128.16.7): BP = the camera's
    ; centre line, cy + 8, where cy = py + z - zg, zg the ground's height
    ; (the ball's own grounded or hidden; the floor's, bz_gh >> 2, airborne
    ; over a FLOOR or GOAL; else held).  Near the window's top or bottom the
    ; fallback LATCHES cy = py until the ball next touches a floor (grounded,
    ; or a contact since it tripped).  The ring above stays on the ball.
    ; (.gline and .cyd bracket the block: bonanzaring's span, 128.16.14)
.gline:
    mov ax, [bz_gz + 1]         ; AX = z, whole px
    mov dx, ax                  ; DX = zg: the ball's own, grounded or hidden
    cmp byte [bz_tube], 0
    jne .zg
    cmp byte [bz_air], 0
    je .zg
    mov dx, [bz_cgz]            ; ...held over no floor
    cmp byte [bz_ghv], 0
    je .zg
    mov dx, [bz_gh]             ; ...the floor's, over a FLOOR or GOAL
    sar dx, 1
    sar dx, 1
.zg:
    mov [bz_cgz], dx
    sub ax, dx                  ; AX = z - zg
    mov bp, [bz_py]
    add bp, 8                   ; BP = the ball's own centre line
    cmp byte [bz_clat + 1], 0
    je .unl
    cmp byte [bz_air], 0        ; latched: released by a floor's touch,
    je .rel                     ; grounded or a contact since the trip
    mov dl, [bz_nland]
    cmp dl, [bz_clat]
    je .cyd                     ; ...or kept: cy = py
.rel:
    mov byte [bz_clat + 1], 0
.unl:
    mov bx, [bz_R0]
    shl bx, cl                  ; T, the window's top line
    mov dx, bp
    sub dx, bx
    sub dx, BZ_CSAFE            ; the centre BZ_CSAFE lines or more inside
    cmp dx, BZ_LINES - 2 * BZ_CSAFE ; both edges (unsigned: above the window
    jb .cgl                     ; trips too): the ground line
    mov dl, [bz_nland]          ; ...else the fallback TRIPS: latched on the
    mov dh, 1                   ; ball's own line
    mov [bz_clat], dx
    jmp short .cyd
.cgl:
    add bp, ax                  ; BP = cy + 8
.cyd:
    cmp byte [bz_cuse], 0
    jne .trickle
    call bz_lattice             ; GLIDE: LATTICE (wave 6b, 128.17.6.2)
    jmp .moved
.trickle:
    ; --- TRICKLE, wave 0's camera (SPEC.md 128.5) ---
    ; vertical: the band [T + 1/3, T + 2/3] of the window's lines
    mov ax, bp                  ; the camera's centre line (the ground line's)
    mov bx, [bz_R0]
    shl bx, cl                  ; T, the window's top line
    mov dx, ax
    sub dx, bx
    mov si, [bz_R0]
    cmp dx, BZ_LINES / 3
    jge .notup
    sub ax, BZ_LINES / 3        ; the top that puts the ball on the band's top
    jge .up
    xor ax, ax
.up:
    shr ax, cl
    mov si, ax
    mov ax, [bz_R0]
    sub ax, BZ_MAXR
    cmp si, ax
    jge .vdone
    mov si, ax
    jmp .vdone
.notup:
    cmp dx, 2 * BZ_LINES / 3
    jle .vdone
    sub ax, 2 * BZ_LINES / 3    ; ...on the band's foot, rounded up a row
    add ax, [bz_rl]
    dec ax
    shr ax, cl
    mov si, ax
    mov ax, [bz_R0]
    add ax, BZ_MAXR
    cmp si, ax
    jle .vdone
    mov si, ax
.vdone:
    mov [bz_R0n], si
    ; horizontal: the dead zone [left + W*2, left + W*6] px
    mov ax, [bz_px]
    add ax, 8                   ; the ball's centre px
    mov bx, [bz_c0]
    shl bx, 1
    shl bx, 1
    shl bx, 1
    sub ax, bx                  ; ...in the window
    mov dx, [bz_W]
    shl dx, 1                   ; a quarter of the window's px
    mov si, [bz_c0]
    cmp ax, dx
    jge .notl
    dec si
    jmp .hdone
.notl:
    mov bx, dx
    shl bx, 1
    add bx, dx                  ; three quarters
    cmp ax, bx
    jle .hdone
    inc si
.hdone:
    mov [bz_c0n], si
.moved:
    call bz_clampwin
    mov byte [bz_full], 0
    mov ax, [bz_R0n]            ; a step past the ring's rules: a full write
    sub ax, [bz_R0]
    mov dx, ax
    call bz_abs
    cmp dx, BZ_MAXR
    ja .full
    mov ax, [bz_c0n]
    sub ax, [bz_c0]
    mov dx, ax
    call bz_abs
    cmp dx, BZ_MAXC
    jbe .decided
.full:
    mov byte [bz_full], 1
.decided:
    mov ax, [bz_R0n]
    sub ax, [bz_R0]
    mov [bz_dr], ax
    mov ax, [bz_c0n]
    sub ax, [bz_c0]
    mov [bz_dc], ax
    mov al, [bz_full]           ; measured: a benchmark's frames but a full
    xor al, 1                   ; write; PLAY and a REPLAY measure nothing,
    and al, [bz_mode]           ; since nothing reads it (bz_mode 1 B and 3 D
                                ; keep the bit, 0 and 2 do not)
    cmp word [bz_mfr], 0ffffh   ; D measures its first 65,535 frames, whose
    jb .m                       ; counts are words, and plays on unmeasured
    or [bz_dtr], al             ; (128.14.7.3: TRUNCATED, when one more would
    xor al, al                  ; have been)
.m:
    mov [bz_meas], al
    ret
.script:
    ; --- bz_camscr's SCRIPTED camera (SPEC.md 128.17.6.7, bbcourse.Glide.
    ; _script): the cycle's (row, column) step, each held BZ_SCR_HOLD frames;
    ; an axis whose step would leave the ball's footprint (128.4's, from
    ; px & ~3) less than BZ_SCR_MX px / BZ_SCR_MY lines inside steps one unit
    ; toward the ball instead.  No heavy rule; LATTICE's state is not touched.
    ; .moved clamps it to the course (a cut step is lost) ---
    mov al, [bz_scnt]
    mov bl, al
    inc ax
    or al, 80h                  ; (bit 7: the script ran, 128.17.6.7's cut)
    mov [bz_scnt], al
    and bx, 38h                 ; (count >> 3) & 7, two bytes an entry
    shr bx, 1
    shr bx, 1
    mov ax, [bz_scyc + bx]      ; AL = its row step, AH = its column's
    push ax
    mov si, bz_R0               ; rows: the footprint's top line, kept
    mov dx, [bz_py]             ; BZ_SCR_MY inside
    sub dx, BZ_SCR_MY
    mov bx, BZ_LINES - BZ_BAL_ROWS - 2 * BZ_SCR_MY
    call .sax                   ; (CL = bz_lsh)
    mov [bz_R0n], ax
    pop ax
    mov al, ah
    mov si, bz_c0               ; columns: its left px (px & ~3), kept
    mov dx, [bz_px]             ; BZ_SCR_MX inside
    and dl, 0fch
    sub dx, BZ_SCR_MX
    mov bx, [bz_W]
    shl bx, 1
    shl bx, 1
    shl bx, 1
    sub bx, BZ_FOOTW + 2 * BZ_SCR_MX
    mov cl, 3
    call .sax
    mov [bz_c0n], ax
    jmp .moved
; one axis: AL = its scripted step, SI -> its position P, CL = log2 of its
; unit, DX = the footprint's first px or line less the margin, BX = the most
; DX may lie past the window's first after the step -> AX: P + the step, or
; one unit toward the ball when that would leave the footprint less than the
; margin inside
.sax:
    cbw
    add ax, [si]
    push ax
    shl ax, cl
    sub dx, ax
    pop ax
    jl .sdec
    cmp dx, bx
    jle .sret
    mov ax, [si]
    inc ax
    ret
.sdec:
    mov ax, [si]
    dec ax
.sret:
    ret
bz_scyc:                        ; the script's cycle: (row, column), R DR D DL
    BZ_SCR_CYCLE                ; L UL U UR (bzcourse.inc)

; -----------------------------------------------------------------------------
; bz_sprite - the frame's SPRITE and SHADOW, from the state the frame's last
; step left (SPEC.md 128.11.9.2, 128.11.9.4).  [bz_px], [bz_py] set.
;   G   = the integer part of (gx + gy) / 2, the ground's screen line (no z)
;   PHY = G & 7 (CGA), (G & 6) | (py & 1) (Hercules: a frame's mid tones are
;         tied to its line's parity); + 2 ((mct >> 2) & 1) mod 8 while STUNNED
;   bz_frm = PHY * 8 + (px & 7), the ROLL frame (stored at shift px & 3)
;   bz_spr = SHATTER (24 - mct) / 6 (BZ_SHA_*) while SHATTERING; SQUASH 0 / 1 / 0 for
;         sqf 6-5 / 4-3 / 2-1 while the ball is AT ITS FLOOR (grounded, or the
;         contact step of a bounce or a contact Hop: airborne, whole z at most
;         bz_gh's floor); else the STRETCH while stf > 0 and the ball is rubber
;         (wave 6, the boost's cue, SPEC.md 128.16.4.4); else the roll frame
; and bz_smsk / bz_sfd, the sprite's mask (row 0, its shift) in the ball part
; and its frame's distance from that mask (bzvideo.inc bz_blit): a squash or
; shatter entry is copy py & 1 of (frame, shift px & 3).  The shadow is a
; CANDIDATE (bz_shc) when the ball is airborne over a FLOOR or GOAL (bz_ghv),
; 2 px or more above it, and the centre's OCCG is clear; its first line
; bz_spy = G - h + Y0 - 3 (h = bz_gh >> 2, whole px) and its mask bz_shm =
; shadow (spy & 1, px & 3).  Clobbers AX, BX, CX, DX.
; -----------------------------------------------------------------------------
%if BZ_BAL_ENT != 160 || BZ_BAL_MASKSH != 80 || BZ_BAL_FRMB != 80 || BZ_BAL_SHDB != 30 || BZ_BAL_SHIFTS != 4
 %error "bz_sprite's offsets assume SPEC.md 128.11.9.1's BZB2"
%endif
%if (BZ_SPR_STR & 3) != 0 || BZ_BAL_NSTR != 1
 %error "bz_sprite's .ent takes the stretch as entry 0 of the table at BZ_BAL_STROFF"
%endif
bz_sprite:
    mov ax, [bz_gx]
    mov dx, [bz_gx + 2]
    add ax, [bz_gy]
    adc dx, [bz_gy + 2]         ; DX:AX = gx + gy, 24.8
    mov al, ah
    mov ah, dl
    shr ax, 1                   ; AX = G = (gx + gy) >> 9
    push ax
    and al, 7                   ; PHY
    cmp byte [bz_herc], 0
    je .phy
    and al, 6
    mov ah, [bz_py]
    and ah, 1
    or al, ah
.phy:
    cmp byte [bz_mst], BZ_ST_STUN ; the dazed wobble: two lines every 4 steps
    jne .f
    mov ah, [bz_mct]
    shr ah, 1
    and ah, 2                   ; 2 ((mct >> 2) & 1)
    add al, ah
    and al, 7
.f:
    mov cl, 3
    shl al, cl
    mov ah, [bz_px]
    and ah, 7
    or al, ah
    xor ah, ah
    mov [bz_frm], ax            ; AL = f
    mov bl, [bz_px]
    and bl, 3                   ; BL = s, the shift
    cmp byte [bz_mst], BZ_ST_SHAT
    jne .sq
%if BZ_SHA_STEPS != BZ_BAL_NSHA * BZ_SHA_FSTEPS
%error "a shatter's steps are not the ball part's shatter frames' (bbcourse SHA_STEPS)"
%endif
    mov al, BZ_SHA_STEPS        ; SHATTER (STEPS - mct) / FSTEPS: 24, 6 (the
    sub al, [bz_mct]            ; tool refuses a shattering material whose
    mov ah, BZ_SPR_SHA - 1      ; HSTEPS is not these)
.d6:
    inc ah
    sub al, BZ_SHA_FSTEPS
    jnc .d6
    mov al, ah
    mov dx, BZ_BAL_SHAOFF
    jmp short .ent
.sq:
    mov cl, [bz_sqf]
    or cl, cl
    jz .st
    cmp byte [bz_air], 0        ; at its floor: grounded, or airborne over the
    je .sqf                     ; floor at its whole z or below
    cmp byte [bz_ghv], 0
    je .st
    mov dx, [bz_gh]
    sar dx, 1
    sar dx, 1
    cmp [bz_gz + 1], dx
    jg .st
.sqf:
    dec cx                      ; SQUASH ((sqf - 1) >> 1) & 1
    shr cl, 1
    and cl, 1
    mov al, BZ_SPR_SQ
    add al, cl
    mov dx, BZ_BAL_SQOFF
.ent:                           ; entry ((k 4 + s) 2 + p) of the table at DX
    mov [bz_spr], al
    and al, 3                   ; k
    shl al, 1
    shl al, 1
    add al, bl
    mov ah, [bz_py]
    and ah, 1
    shl al, 1
    or al, ah
    xor ah, ah                  ; x 160 = (i << 5) x 5, by shifts (128.9 item
    mov cl, 5                   ; 1's no-MUL rule; i <= 31)
    shl ax, cl
    add dx, ax
    shl ax, 1
    shl ax, 1
    add ax, dx
    mov [bz_smsk], ax
    mov word [bz_sfd], BZ_BAL_ENT / 2
    jmp short .shadow
.st:                            ; wave 6: the boost's STRETCH while stf > 0
    cmp byte [bz_stf], 0        ; (SPEC.md 128.16.4.4), after the shatter and
    je .roll                    ; the squash; rubber's part alone has one, so
    cmp byte [bz_mat], BZ_MAT_RUBBER ; a pad's swap inside its four steps shows
    jne .roll                   ; the new ball rolling, never past a part's end
    mov al, BZ_SPR_STR
    mov dx, BZ_BAL_STROFF
    jmp short .ent
.roll:
    mov [bz_spr], al            ; ROLL f, at shift s: its mask MASKOFF + 80 s,
    sub al, bl                  ; its frame FRMOFF + 80 f: x 80 = (x << 4) x 5
    mov cl, 4                   ; by shifts (f - s and s, both under 256)
    shl ax, cl                  ; AX = 16 (f - s) (AH was 0)
    mov dx, ax
    shl ax, 1
    shl ax, 1
    add ax, dx
    add ax, BZ_BAL_FRMOFF - BZ_BAL_MASKOFF
    mov [bz_sfd], ax
    mov al, bl
    cbw
    shl ax, cl                  ; 16 s
    mov dx, ax
    shl ax, 1
    shl ax, 1
    add ax, dx
    add ax, BZ_BAL_MASKOFF
    mov [bz_smsk], ax
.shadow:
    pop ax                      ; AX = G
    mov byte [bz_shc], 0
    cmp byte [bz_ghv], 0        ; airborne over a FLOOR or GOAL
    je .out
    test byte [bz_nbr + BZN_C + 3], BZ_FL_OCCG
    jnz .out                    ; ...whose cell cannot hide a grounded ball
    mov dx, [bz_gh]
    sar dx, 1
    sar dx, 1                   ; DX = h, whole px
    sub ax, dx                  ; spy = G - h + Y0 - 3
    add ax, [bz_y0]
    sub ax, 3
    mov cx, [bz_gz + 1]
    sub cx, dx
    cmp cx, 2                   ; ...2 px or more above it
    jl .out
    mov [bz_spy], ax
    mov byte [bz_shc], 1
    and ax, 1                   ; its mask: shadow (spy & 1, s): i = 4 p + s
    shl al, 1
    shl al, 1
    add al, bl
    shl ax, 1                   ; x 30 = (i << 5) - (i << 1), by shifts
    mov dx, ax
    mov cl, 4
    shl ax, cl
    sub ax, dx
    add ax, BZ_BAL_SHDOFF
    mov [bz_shm], ax
.out:
    ret

; -----------------------------------------------------------------------------
; bz_lattice - GLIDE, LATTICE since wave 6b (SPEC.md 128.17.6.2, 128.17.6.3:
; bbcourse.Glide._lattice exactly), once a frame after the ring and the
; ground line.  The TRACKED POINT is the ball's centre across (bz_px + 8) and
; the camera's centre line down (BP = cy + 8, the ground line's); while a
; tube carries the ball it is the tube's EXIT (bz_lexit: the pre-aim).  Each
; axis: bz_lat (steps 1 - 7), the heavy rule (bz_lhv, step 8), the move
; (bz_lmove, step 9) - or, at rest with the point inside its stored band
; (BZL_BLO .. BZL_BHI), none of them: no step, nothing changes, so the
; frame's test is two comparisons inline (most frames are such).  Counts
; bz_nhvy, bz_nhedge, bz_nwr, bz_nwc.  Sets bz_c0n, bz_R0n.  Preserves
; nothing.
; -----------------------------------------------------------------------------
bz_lattice:
    mov bx, [bz_px]
    add bx, 8                   ; BX = the ball's centre px
    cmp byte [bz_tube], 0
    je .pt
    call bz_lexit               ; a tube in transit: its exit (BX, BP)
.pt:
    cmp byte [bz_heavy], 0      ; THE HEAVY FRAME (128.17.6.3), counted
    je .lt
    inc word [bz_nhvy]
    cmp word [bz_hedr], 0       ; (bz_hedr, bz_hedc: the edge clause)
    je .lt
    inc word [bz_nhedge]
.lt:
    mov dx, [bz_c0]             ; ACROSS
    mov si, bz_lax
    cmp byte [si + BZL_S], 0    ; at rest inside its band: no step, and
    jne .x                      ; nothing changes (steps 1 and 4, inline)
    cmp bx, [si + BZL_BLO]
    jl .x
    cmp bx, [si + BZL_BHI]
    jle .xr
.x:
    push bp
    call bz_lat
    mov di, bz_nwc
    mov bl, [bz_hedc]           ; (released by the edge clause; level 1
    xor bh, bh                  ; withholds a column, level 2 too)
    mov cx, BZ_PF_NEARL << 8
    call bz_lhv                 ; (and bz_lmove)
    pop bp
.xr:
    mov [bz_c0n], dx
    mov bx, bp
    mov dx, [bz_R0]             ; DOWN
    mov si, bz_lay
    cmp byte [si + BZL_S], 0
    jne .y
    cmp bx, [si + BZL_BLO]
    jl .y
    cmp bx, [si + BZL_BHI]
    jle .yr
.y:
    call bz_lat
    mov di, bz_nwr
    mov bl, [bz_hedr]           ; (level 1 lets one row through, level 2
    mov bh, 1                   ; none on the CGA and one on the Hercules)
    mov cl, [bz_herc]
    mov ch, BZ_PF_NEART
    call bz_lhv
.yr:
    mov [bz_R0n], dx
    ret

; -----------------------------------------------------------------------------
; bz_lat - LATTICE on one axis, steps 1 - 7 (SPEC.md 128.17.6.2: bbcourse.
; LatAxis.decide).  SI = its state (BZL_*; its constants at [SI + BZL_K],
; BZK_*), BX = the tracked point b, DX = the window's position P.  In the
; axis's px or lines: off = b - P u.
;   1. the BAND (bz_lband's, kept for this P): lo = A, less Hr after a pan +;
;      hi = Wp - A, plus Hr after a pan -.  The point wants a pan w = +1 past
;      hi, -1 below lo, else 0.
;   2. the LATTICE target for a direction (bz_lcand).
;   3. w not 0: the pan running that way extends FORWARD to it; else a pan
;      STARTS when it lies beyond P that way (fast clear, since 9).  w 0 and
;      a pan running: it extends forward.
;   4. at rest: no step.  5. w 0 and the point back inside its lead (off < T
;      going +, > Wp - T going -): the pan STOPS, no step.
;   6. FAST rises (never falls inside a pan): a tube, the ring's x verdict
;      (across), the point past the URGENT edge (off < Ef or > Wp - Ef).
;   7. the step: across since = min(9, since + 1), then a column when since
;      is 2 or more (1 when fast); down a row, two when fast; never more than
;      |tgt - P|.
; -> AX = the step, unsigned, before the heavy rule.  Preserves SI, DX.
; Clobbers BX, CX, DI, BP.
; -----------------------------------------------------------------------------
bz_lat:
    mov di, [si + BZL_K]
    mov cl, [si + BZL_SH]
    mov bp, dx
    shl bp, cl
    neg bp
    add bp, bx                  ; BP = off
    mov ch, -1                  ; 1. CH = w, from the band (bz_lband's)
    cmp bx, [si + BZL_BLO]
    jl .want
    mov ch, 1
    cmp bx, [si + BZL_BHI]
    jg .want
    mov ch, 0
    mov al, [si + BZL_S]
    or al, al
    jnz .ext                    ; inside the band: a running pan extends
.zero:
    xor ax, ax                  ; 4. at rest
    ret
.want:
    mov al, ch
    cmp al, [si + BZL_S]
    je .ext                     ; 3. that way already: it may extend
    call bz_lcand               ; 2. BX = the target that way: a pan
    cmp bx, dx                  ; STARTS when it is beyond P that way
    je .cont                    ; (positions are 0 or more, so unsigned:
    sbb ah, ah                  ; AH's sign is the target's side's XOR
    xor ah, al                  ; the direction's)
    js .cont
    mov [si + BZL_S], al
    mov word [si + BZL_FAST], 0900h ; fast clear, since 9
    jmp short .tgt
.ext:
    call bz_lcand
    cmp bx, [si + BZL_TGT]      ; the target moves FORWARD only (the same
    je .cont                    ; test as the start's)
    sbb ah, ah
    xor ah, al
    js .cont
.tgt:
    mov [si + BZL_TGT], bx
.cont:
    mov al, [si + BZL_S]
    or al, al
    jz .zero                    ; 4.
    or ch, ch
    jnz .rate
    or al, al                   ; 5. the point back inside its lead: STOP
    js .sneg
    cmp bp, [di + BZK_T]
    jl .stop
    jmp short .rate
.sneg:
    cmp bp, [di + BZK_WPT]
    jle .rate
.stop:
    mov byte [si + BZL_S], 0
    jmp short .zero
.rate:
    mov al, [bz_tube]           ; 6. a tube, the ring (across), the urgent
    cmp byte [di + BZK_COLS], 0 ; edge: fast
    je .cz
    or al, [bz_gfast]
.cz:
    or al, al
    jnz .fast
    cmp bp, [di + BZK_EF]
    jl .fast
    cmp bp, [di + BZK_WPE]
    jle .step
.fast:
    mov byte [si + BZL_FAST], 1
.step:
    mov al, [si + BZL_FAST]     ; 7. down: one row, two when fast
    cbw
    inc ax
    cmp byte [di + BZK_COLS], 0
    je .min
    mov al, [si + BZL_SINCE]    ; across: since + 1, at most 9 ...
    cmp al, 9
    adc al, 0
    mov [si + BZL_SINCE], al
    mov ah, 2                   ; ...a column when since reaches 2, or 1
    sub ah, [si + BZL_FAST]     ; when fast
    cmp al, ah
    sbb ax, ax
    inc ax
.min:
    mov bx, [si + BZL_TGT]      ; never past the target
    sub bx, dx
    jns .ab
    neg bx
.ab:
    cmp ax, bx
    jbe .out
    xchg ax, bx
.out:
    ret

; bz_lcand - LATTICE's TARGET for direction AL (SPEC.md 128.17.6.2 step 2,
; LatAxis.cand): with t = b - T going +, floor(t / uS) S; with t = b - (Wp -
; T) going -, ceil(t / uS) S; 0 when t <= 0; at most the range's top - so the
; same place always gives the same framing, the point at least T inside the
; trailing side.  uS is a power of two (BZK_M + 1), so the rounding is a
; mask and the units a shift.  SI, DI, BX = b as bz_lat's -> BX.  Clobbers CL.
bz_lcand:
    or al, al
    js .neg
    sub bx, [di + BZK_T]
    jmp short .t
.neg:
    sub bx, [di + BZK_WPT]
    jle .z
    add bx, [di + BZK_M]
.t:
    jle .z
    or bx, [di + BZK_M]
    xor bx, [di + BZK_M]
    mov cl, [si + BZL_SH]
    shr bx, cl
    cmp bx, [si + BZL_MX]
    jle .r
    mov bx, [si + BZL_MX]
.r:
    ret
.z:
    xor bx, bx
    ret

; bz_lhv - THE HEAVY RULE as a bounded delay, step 8 (SPEC.md 128.17.6.3,
; bbcourse.Glide._lattice): on a heavy frame whose edge clause does not
; release the axis, level 2 withholds all but its limit (CL), level 1 all but
; its limit (BH) only when the slab is near the edge the pan heads for
; (bz_pflag's bit CH heading -, the next bit heading +).  An axis whose
; `held` has reached its cap (BZ_LAH2, BZ_LAH1) takes its step whatever the
; level, and a withheld step is never made up.  `held` counts the withheld
; steps since the axis last stepped: a withholding adds one, a step left
; after the rule clears it.  SI = the axis's state, AX = its step, BL = 1
; when the edge clause releases it, DI = its withheld counter (bz_nwc,
; bz_nwr).  The step it leaves goes on into bz_lmove (DX = P -> DX).
; Clobbers AX, BX, CH.
bz_lhv:
    or ax, ax
    jz bz_lmove                 ; no step to take: held stays
    cmp byte [bz_heavy], 0
    je .go
    or bl, bl
    jnz .go
    cmp byte [bz_heavy], 2
    jne .l1
    cmp byte [si + BZL_HELD], BZ_LAH2
    jae .go                     ; level 2 capped: the step goes
    mov bh, cl                  ; ...else every axis, to its limit
    jmp short .wh
.l1:
    cmp byte [si + BZL_S], 0    ; level 1: only toward the near edge
    jl .side
    shl ch, 1
.side:
    test [bz_pflag], ch
    jz .go
    cmp byte [si + BZL_HELD], BZ_LAH1
    jae .go                     ; ...capped: the step goes
.wh:
    cmp al, bh
    jbe .go
    sub al, bh                  ; (AH = 0: the step is at most 2)
    add [di], ax                ; withheld
    mov al, bh
    inc byte [si + BZL_HELD]
.go:
    or ax, ax
    jz bz_lmove
    mov byte [si + BZL_HELD], 0
                                ; (on into bz_lmove)
; bz_lmove - step 9: P += s x step (AX, unsigned; DX = P -> DX); a window that
; moved sets last = s and, across, since 0 (unread down); P at the target
; ends the pan; a window that moved takes the band at the new P (shifted by
; the step, or bz_lband's whole when `last` changed).  SI = the axis's state.
; Clobbers AX, BX, CL, DI.
bz_lmove:
    or ax, ax
    jz .out                     ; (a pan never sits on its target unmoved)
    mov bl, [si + BZL_S]
    mov byte [si + BZL_SINCE], 0
    or bl, bl
    jns .add
    neg ax
.add:
    add dx, ax
    cmp bl, [si + BZL_LAST]
    mov [si + BZL_LAST], bl
    jne .whole                  ; `last` changed: the band whole ...
    mov cl, [si + BZL_SH]
    shl ax, cl                  ; ...else it moves with the window
    add [si + BZL_BLO], ax
    add [si + BZL_BHI], ax
    jmp short .tgt
.whole:
    call bz_lband
.tgt:
    cmp dx, [si + BZL_TGT]
    jne .out
    mov byte [si + BZL_S], 0
.out:
    ret
; bz_lband - the axis's BAND at position DX (step 1's, SPEC.md 128.17.6.2),
; in the tracked point's px or lines: BZL_BLO = P u + A, less Hr after a pan
; +; BZL_BHI = P u + Wp - A, plus Hr after a pan -.  Kept while P and `last`
; hold, so a frame at rest inside it does nothing else (bz_lattice).  SI =
; the axis's state.  Clobbers AX, BX, CL, DI.
bz_lband:
    mov di, [si + BZL_K]
    mov cl, [si + BZL_SH]
    mov ax, dx
    shl ax, cl
    mov bx, ax
    add ax, [di + BZK_A]
    cmp byte [si + BZL_LAST], 0
    jle .lo
    sub ax, [di + BZK_HR]
.lo:
    mov [si + BZL_BLO], ax
    add bx, [di + BZK_WPA]
    cmp byte [si + BZL_LAST], 0
    jge .hi
    add bx, [di + BZK_HR]
.hi:
    mov [si + BZL_BHI], bx
    ret

; bz_lexit - a TUBE's tracked point (SPEC.md 128.17.6.2's pre-aim, Glide.
; _exit_point): the END (ex, ey, ez) of its record's last segment, projected as
; bz_derive projects the ball - BX = ex - ey + X0 - 8 + 8 across, BP = ((ex +
; ey) >> 1) - ez + Y0 - 13 + 8 down: the centre.  Clobbers AX, DX, SI.
bz_lexit:
    push es
    mov es, [bz_cseg]
    mov bl, [bz_tube]
    xor bh, bh
    dec bx
    call bz_lrecsi              ; ES:SI = its record
    mov al, [es:si + BZP_TNSEG]
    mov ah, BZ_SEGREC
    mul ah
    add ax, [es:si + BZP_TSEGS]
    xchg ax, si                 ; SI = the end of its last segment
    mov ax, [es:si + 8 - BZ_SEGREC] ; ex
    mov dx, [es:si + 10 - BZ_SEGREC] ; ey
    mov bx, ax
    sub bx, dx
    add bx, [bz_x0]             ; (X0 - 8, the ball's left, + 8)
    add ax, dx
    sar ax, 1
    sub ax, [es:si + 12 - BZ_SEGREC] ; ez
    add ax, [bz_y0]
    sub ax, 13 - 8              ; (Y0 - 13, the ball's top, + 8)
    xchg ax, bp
    pop es
    ret

; bz_latrst - LATTICE's axes at REST (the first frame and a cut, SPEC.md
; 128.17.6.2; and GLIDE resumed after TRICKLE): s, last, fast and held 0,
; since 9; each axis's unit, range, constants (the card's) and band at the
; window as it stands; the script's count 0.  Clobbers AX, BX, CL, DX, SI, DI.
bz_latrst:
    mov byte [bz_scnt], 0
    mov si, bz_lax
    mov al, [bz_herc]
    mov ah, BZK_SIZE
    mul ah
    add ax, bz_klat
    mov [si + BZL_K], ax
    mov bx, [bz_cmax]
    mov dx, [bz_c0]
    mov ah, 3                   ; across: u = 8 px
    call .one
    mov si, bz_lay
    mov word [si + BZL_K], bz_klat + 2 * BZK_SIZE
    mov bx, [bz_rmax]
    mov dx, [bz_R0]
    mov ah, [bz_lsh]            ; down: u = rl lines
.one:
    mov word [si + BZL_S], 0    ; s, last
    mov word [si + BZL_FAST], 0900h ; fast, since 9
    xor al, al
    mov [si + BZL_HELD], ax     ; held, the unit's shift
    mov [si + BZL_MX], bx
    jmp bz_lband                ; (tgt: set at a pan's start)

; LATTICE's CONSTANTS (BZK_*; bbcourse.lat_consts, bzcourse.inc's BZ_LAX_*,
; BZ_LAY_*): across on the CGA, across on the Hercules, down
%macro BZ_KLAT 7                ; A, Hr, T, Ef, Wp, uS - 1, across
    dw %1, %5 - %1, %2, %3, %5 - %3, %4, %5 - %4, %6
    db %7
%endmacro
bz_klat:
    BZ_KLAT BZ_LAX_A_C, BZ_LAX_HR_C, BZ_LAX_T_C, BZ_LAX_EF_C, 8 * BZ_WC, BZ_LAX_S * 8 - 1, 1
    BZ_KLAT BZ_LAX_A_H, BZ_LAX_HR_H, BZ_LAX_T_H, BZ_LAX_EF_H, 8 * BZ_WH, BZ_LAX_S * 8 - 1, 1
    BZ_KLAT BZ_LAY_A, BZ_LAY_HR, BZ_LAY_T, BZ_LAY_EF, BZ_LINES, BZ_LAY_SL - 1, 0
%if $ - bz_klat != 3 * BZK_SIZE
 %error "bz_klat's rows are BZK_SIZE bytes"
%endif

; CF = 1 when the ball's footprint (bz_px, bz_py: 128.4's 20 x 16 from px & ~3,
; as bz_mkboxes's) is NOT wholly inside the current window (bz_c0, bz_R0).
; Clobbers AX, CX, DX.
bz_outwin:
    mov ax, [bz_px]
    mov cl, 3
    shr ax, cl                  ; the footprint's first word column
    cmp ax, [bz_c0]
    jb .out                     ; (CF = 1: left of the window)
    mov ax, [bz_px]
    shr ax, 1
    shr ax, 1
    add ax, BZ_BAL_RB - 1
    shr ax, 1                   ; ...its last
    mov dx, [bz_c0]
    add dx, [bz_W]
    cmp ax, dx
    cmc                         ; CF = 1: at or past the window's right
    jc .out
    mov ax, [bz_R0]
    mov cl, [bz_lsh]
    shl ax, cl                  ; the window's top line
    mov dx, [bz_py]
    cmp dx, ax
    jb .out                     ; CF = 1: above it
    add ax, BZ_LINES - BZ_BAL_ROWS
    cmp ax, dx                  ; CF = 1: its foot below the window's
.out:
    ret

; [bz_R0n], [bz_c0n] clamped to the course.  Clobbers AX.
bz_clampwin:
    mov ax, [bz_R0n]
    or ax, ax
    jge .r
    xor ax, ax
.r:
    cmp ax, [bz_rmax]
    jle .r2
    mov ax, [bz_rmax]
.r2:
    mov [bz_R0n], ax
    mov ax, [bz_c0n]
    or ax, ax
    jge .c
    xor ax, ax
.c:
    cmp ax, [bz_cmax]
    jle .c2
    mov ax, [bz_cmax]
.c2:
    mov [bz_c0n], ax
    ret

; -----------------------------------------------------------------------------
; bz_mkboxes - the frame's boxes (SPEC.md 128.4, 128.11.10.1).  The FOOTPRINTS,
; as rects in words x lines: the ball's new one (its 5 bytes x 16 lines) and
; its old one, and the SHADOW's new one (the ball's columns, lines spy .. spy +
; 5) when it is drawn this frame and its old one when it was drawn last frame.
; They make at most FOUR boxes: the BALL GROUP, old and new as ONE box (their
; union) when that fits BZ_BOXW x BZ_BOXH, else two; the SHADOW GROUP the same;
; and the two groups ONE box when each is one box and their union fits.  A
; full write needs only the new ones.  WHILE THE PASS RUNS (bz_ogate: the
; centre's cell has OCC airborne or OCCG grounded, or a poke) the shadow is drawn only when it shares
; the ball's box, and left out otherwise (SPEC.md 128.11.9.4) - its old
; footprint is still restored.  Each box is clipped to the NEW window; what an
; old footprint loses to the clip needs no restoring (SPEC.md 128.4).  The
; boxes are SORTED by first line (the write order, 128.11.10.3), and the later
; box of two of one group gets their overlap band (bz_band: it skips those
; words when written, 128.9 item 5); boxes of different groups that overlap
; hold the same bytes there and are written whole.  AN IDLE BALL - the same
; position as last frame, no scroll, the same cell row, height and air flag
; (the same occluders), the same SPRITE and the same shadow (drawn or not, and
; its line) - needs NO box: the card already holds it (128.11.10.4).
; Preserves nothing.
; -----------------------------------------------------------------------------
%macro BZ_RPUT 0                ; the rect at SI copied to DI, DI past it (SI too).
    movsw                       ; ES = ours
    movsw
    movsw
    movsw
%endmacro
bz_mkboxes:
    push ds
    pop es
    mov ax, [bz_R0n]            ; the new window's top line (the clip, the
    mov cl, [bz_lsh]            ; pass, the column's split, the lateness)
    shl ax, cl
    mov [bz_wtop], ax
    call bz_pstrip              ; a strip meeting the slab: its clipped box
    call bz_povr                ; (the contact group), and the slab's one
                                ; decision, under or over (SPEC.md 128.12.4.5)
    mov ah, BZ_FOCC             ; the occluder pass's gate (bz_occ): AIRBORNE
    cmp byte [bz_air], 0        ; the centre's OCC; GROUNDED (so at its
    jne .og                     ; floor) its OCCG, set wherever a grounded
    mov ah, BZ_FL_OCCG          ; ball meets a laid record (SPEC.md 128.11.4.3,
.og:                            ; 128.11.10.2); or a harness's poke (bz_pokd
    mov al, [bz_nbr + BZN_C + 3] ; is 0 or 1)
    and al, ah
    or al, [bz_pokd]
    mov [bz_ogate], al
    mov ax, [bz_px]             ; BP = 0 when the ball has not moved and the
    mov bp, ax                  ; window has not either (the old px, py are
    xchg ax, [bz_opx]           ; this frame's from here on)
    sub bp, ax
    mov ax, [bz_py]
    mov dx, ax
    xchg ax, [bz_opy]
    sub dx, ax
    or bp, dx
    or bp, [bz_dr]
    or bp, [bz_dc]
    mov ax, [bz_sb]             ; ...and the ball's cell row, height and air
    mov dx, ax                  ; flag have not either: with any of them
    xchg ax, [bz_osb]           ; changed the occluders may lay back other
    sub dx, ax                  ; pixels at the same picture position
    or bp, dx                   ; (SPEC.md 128.10.8 item 2)
    mov ax, [bz_gz + 1]
    mov dx, ax
    xchg ax, [bz_ozb]
    sub dx, ax
    or bp, dx
    mov al, [bz_air]
    xchg al, [bz_oair]
    xor al, [bz_oair]
    mov ah, [bz_spr]            ; ...the same sprite (128.11.10.4)
    xchg ah, [bz_ospr]
    xor ah, [bz_ospr]
    or bp, ax
    mov ax, 8000h               ; ...and the same shadow: this frame's
    cmp byte [bz_shc], 0        ; candidate against what was drawn
    je .s0
    mov ax, [bz_spy]
.s0:
    mov dx, 8000h
    cmp byte [bz_sov], 0
    je .s1
    mov dx, [bz_sox0 + 4]
.s1:
    xor ax, dx
    or bp, ax
    mov al, [bz_ctype]          ; ...and no contact group: a frame with one
    or al, [bz_hidn]            ; is never idle (SPEC.md 128.12.4.3), nor a
    cbw                         ; hidden ball's, whose capture frame restores
    or bp, ax                   ; the footprint it was drawn in (128.12.6.1)
    mov word [bz_nbox], 0       ; (the new footprints are bz_foot's, rule 0)
    mov word [bz_boxp], bz_boxes
    mov byte [bz_ohold], 0       ; the old footprints count unless a full write
    cmp byte [bz_full], 0       ; or the first frame
    jne .go
    cmp byte [bz_oldv], 0
    je .go
    mov byte [bz_ohold], 1
    or bp, bp
    jnz .go
    ret                         ; idle: nothing to compose or write
.go:
    mov al, [bz_shc]
    mov [bz_snv], al
.groups:
    mov di, bz_gr               ; DI = the next rect
    cmp byte [bz_hidn], 0       ; a HIDDEN ball (in a tube, or holed) has no
    jne .hid                    ; new footprint: its old one alone, restored
    ; THE BALL GROUP: the union of the old and the new, or each
    mov si, bz_nfx0
    cmp byte [bz_ohold], 0
    je .bput
    mov bx, bz_ofx0
    call bz_union
    jnc .bu
    mov si, bz_ofx0
    BZ_RPUT
    mov si, bz_nfx0
    jmp short .bput
.bu:
    mov si, bz_ur
.bput:
    BZ_RPUT
.sgrp:
    mov dx, di                  ; DX = the shadow group's first rect
    ; THE SHADOW GROUP: the old (drawn last frame) and the new (drawn now)
    cmp byte [bz_ohold], 0
    je .sn
    cmp byte [bz_sov], 0
    je .sn
    mov si, bz_sox0
    cmp byte [bz_snv], 0
    je .sput                    ; the old alone: its restoring box
    mov bx, bz_snx0
    call bz_union
    jnc .su
    BZ_RPUT                     ; two: the old, then the new
    jmp short .snew
.su:
    mov si, bz_ur
    jmp short .sput
.sn:
    cmp byte [bz_snv], 0
    je .sdone
.snew:
    mov si, bz_snx0
.sput:
    BZ_RPUT
.sdone:
    ; ONE BOX when each group is one box and their union fits
    cmp dx, bz_gr + 8
    jne .split
    cmp di, bz_gr + 16
    jne .split
    mov si, bz_gr
    mov bx, bz_gr + 8
    call bz_union
    jc .split
    mov di, bz_gr
    mov si, bz_ur
    BZ_RPUT                     ; (DX = bz_gr + 8: the one rect is group 0)
    jmp short .emit
.hid:
    cmp byte [bz_ohold], 0      ; (SPEC.md 128.12.6.1: the capture's frame
    je .sgrp                    ; restores it, the frames after compose
    mov si, bz_ofx0             ; nothing for the ball)
    BZ_RPUT
    jmp short .sgrp
.split:
    cmp byte [bz_ogate], 0      ; the pass runs and the shadow is not in the
    je .emit                    ; ball's box: not drawn this frame
    cmp byte [bz_snv], 0
    je .emit
    mov byte [bz_snv], 0
    jmp .groups
.emit:
    ; THE CONTACT GROUP (SPEC.md 128.12.4.3): bz_props's lane or slab, merged
    ; into the ball's group when that is one rect and their union fits, else
    ; a rect of its own - and when that would be a FIFTH, the shadow's new
    ; footprint is left out and its old one restored, as on an OCC frame.
    ; The PLATFORM's box (bz_ctype 2) fits when the union is BZ_BOXW x
    ; BZ_BOXL: THE RIDE BOX, one compose and one write of the slab and the
    ; ball it carries (128.13.4.1); a lane's and a strip's, BZ_BOXH
    mov word [bz_cgr], 0
    mov al, [bz_ctype]
    or al, al
    je .eall
    cmp dx, bz_gr + 8
    jne .cadd
    mov si, bz_gr
    mov bx, bz_crect
    cmp al, 2
    jne .cun
    call bz_unionl
    jmp short .cu2
.cun:
    call bz_union
.cu2:
    jc .cadd
    push di
    mov di, bz_gr
    mov si, bz_ur
    BZ_RPUT
    pop di
    jmp short .ct2
.cadd:
    cmp di, bz_gr + 32
    jb .cput
    mov byte [bz_snv], 0        ; (four rects need the shadow's new one)
    jmp .groups
.cput:
    mov [bz_cgr], di
    mov si, bz_crect
    BZ_RPUT
.ct2:
    ; THE LIFT'S BOX BESIDE A LIGHTING POST (bz_pflag bit 2, SPEC.md
    ; 128.12.5.2): merged into the ball's group (up to BZ_BOXL lines, the
    ; ride box's limit) or the post's (BZ_BOXH) when the union fits, else a
    ; rect of its own when there is room - else the post WAITS a frame
    ; (bz_pyield: its map words back) and the box is the contact group (on a
    ; crowded frame bz_props made the BOX wait instead when it could, 128.13.4.3)
    mov word [bz_cgr2], 0
    test byte [bz_pflag], 4
    jz .eall
    mov bx, bz_crect2
    mov si, bz_gr
    cmp dx, bz_gr + 8
    jne .ct2b
    call bz_unionl              ; (the ride box's limit, as above)
    jnc .ct2m
.ct2b:
    mov si, [bz_cgr]
    or si, si
    jz .ct2c
    call bz_union
    jc .ct2c
.ct2m:
    push di
    mov di, si
    mov si, bz_ur
    BZ_RPUT
    pop di
    jmp short .eall
.ct2c:
    cmp di, bz_gr + 32
    jb .ct2p
    call bz_pyield
    jmp .groups
.ct2p:
    mov [bz_cgr2], di
    mov si, bz_crect2
    BZ_RPUT
.eall:
    ; the rects as boxes, each clipped to the new window: group 0 the ball's,
    ; 1 the shadow's, 2 the contact's
    mov [bz_sgr], dx            ; (the shadow group's first rect)
    mov bp, di                  ; BP = the rects' end
    mov si, bz_gr
.e:
    cmp si, bp
    jae .sort
    xor al, al
    cmp si, [bz_sgr]
    jb .g
    inc ax
    cmp si, [bz_cgr]
    je .g2
    cmp si, [bz_cgr2]
    jne .g
.g2:
    inc ax
.g:
    mov [bz_grp], al
    lodsw
    mov bx, [si]
    mov cx, [si + 2]
    mov dx, [si + 4]
    add si, 6
    call bz_addbox              ; (keeps SI and BP)
    jmp short .e
.sort:
    ; in the order of their first lines (at most four: a bubble sort)
    mov cx, [bz_nbox]
    dec cx
    jle .sorted
.pass:
    push cx
    mov si, bz_boxes
.cmp:
    mov ax, [si + 2]
    cmp ax, [si + BZ_BOXD + 2]
    jle .inord
    xchg ax, [si + BZ_BOXD + 2] ; a swap: the rect and the group.  The buffers
    mov [si + 2], ax            ; stay where they are (four alike, none
    mov ax, [si]                ; composed yet) and no box has a band yet
    xchg ax, [si + BZ_BOXD]     ; (+10 is 0 in both; +12 .. +17 are read only
    mov [si], ax                ; under a band, which bz_band lays whole)
    mov ax, [si + 4]
    xchg ax, [si + BZ_BOXD + 4]
    mov [si + 4], ax
    mov ax, [si + 6]
    xchg ax, [si + BZ_BOXD + 6]
    mov [si + 6], ax
    mov al, [si + 18]
    xchg al, [si + BZ_BOXD + 18]
    mov [si + 18], al
.inord:
    add si, BZ_BOXD
    loop .cmp
    pop cx
    loop .pass
.sorted:
    ; the overlap band: the later box of a group skips what the earlier wrote
    mov di, bz_boxes + BZ_BOXD
    mov cx, [bz_nbox]
    dec cx
    jle .count
.bj:
    mov si, bz_boxes
.bi:
    mov al, [si + 18]
    cmp al, [di + 18]
    jne .bnext
    call bz_band
.bnext:
    add si, BZ_BOXD
    cmp si, di
    jb .bi
    add di, BZ_BOXD
    loop .bj
.count:
    cmp byte [bz_snv], 0        ; the instruments: shadow frames, and frames
    je .c2                      ; of two boxes or more, three or more
    inc word [bz_nshd]
.c2:
    mov ax, [bz_nbox]
    cmp ax, 2
    jb .out
    inc word [bz_n2bx]
    cmp ax, 3
    jb .out
    inc word [bz_n3bx]
.out:
    ret

; bz_union - the union of the rects at SI and BX into bz_ur: CF = 1 when it
; does not fit one box (BZ_BOXW words x BZ_BOXH lines).  bz_unionl - the same
; held to BZ_BOXL lines: the PLATFORM's contact group with the ball's (the
; RIDE BOX, SPEC.md 128.13.4.1) - bz_union's, and when that refuses a union
; that is narrow enough, its height asked again against BZ_BOXL (the width
; refused first, so the lines are in bz_ur whenever it gets that far): the
; common caller pays no limit register (128.13.4.5).  Clobbers AX.
bz_unionl:
    call bz_union
    jnc .x
    mov ax, [bz_ur + 2]
    sub ax, [bz_ur]
    cmp ax, BZ_BOXW - 1
    ja .no
    mov ax, [bz_ur + 6]
    sub ax, [bz_ur + 4]
    cmp ax, BZ_BOXL             ; CF = it fits ...
    cmc                         ; ...turned round
.x:
    ret
.no:
    stc
    ret
bz_union:
    mov ax, [si]
    cmp ax, [bx]
    jle .x0
    mov ax, [bx]
.x0:
    mov [bz_ur], ax
    mov ax, [si + 2]
    cmp ax, [bx + 2]
    jge .x1
    mov ax, [bx + 2]
.x1:
    mov [bz_ur + 2], ax
    sub ax, [bz_ur]
    cmp ax, BZ_BOXW - 1
    ja .no
    mov ax, [si + 4]
    cmp ax, [bx + 4]
    jle .y0
    mov ax, [bx + 4]
.y0:
    mov [bz_ur + 4], ax
    mov ax, [si + 6]
    cmp ax, [bx + 6]
    jge .y1
    mov ax, [bx + 6]
.y1:
    mov [bz_ur + 6], ax
    sub ax, [bz_ur + 4]
    cmp ax, BZ_BOXH             ; CF = it fits (h - 1 < the limit) ...
    cmc                         ; ...turned round
    ret
.no:
    stc
    ret

; bz_band - the overlap of box SI (written first) and box DI (later, the same
; group), in DI's terms (SPEC.md 128.9 item 5): its words [xa, xb) on its lines
; whose lines-left count is in (xlo, xhi]; xhi stays 0 when they are apart.
; Clobbers AX, BX, DX.
bz_band:
    push cx
    mov ax, [si]                ; x: [max(x0, x0'), min(x0 + w, x0' + w'))
    mov bx, [di]
    cmp ax, bx
    jge .xl
    mov ax, bx
.xl:
    mov cx, [si]
    add cx, [si + 4]
    mov dx, bx
    add dx, [di + 4]
    cmp cx, dx
    jle .xr
    mov cx, dx
.xr:
    cmp ax, cx
    jge .out                    ; apart in x
    sub ax, bx
    sub cx, bx
    mov [di + 14], ax
    mov [di + 16], cx
    mov ax, [si + 2]            ; y: [max(y0, y0'), min(y0 + h, y0' + h'))
    mov bx, [di + 2]
    cmp ax, bx
    jge .yt
    mov ax, bx
.yt:
    mov cx, [si + 2]
    add cx, [si + 6]
    mov dx, bx
    add dx, [di + 6]            ; DX = y0' + h', the later box's end
    cmp cx, dx
    jle .yb
    mov cx, dx
.yb:
    cmp ax, cx
    jge .out                    ; apart in y
    sub dx, ax
    mov [di + 10], dx           ; the band's first line has xhi lines left...
    add dx, ax
    sub dx, cx
    mov [di + 12], dx           ; ...and the line after its last, xlo
.out:
    pop cx
    ret

; AX = x0, BX = x1 (words), CX = y0, DX = y1 (lines), inclusive: clipped to
; the new window and, if anything is left, appended to bz_boxes as group
; [bz_grp] with no overlap band, its buffer the next of bz_boxbuf's four.
; ES = ours.  Clobbers AX-DX, DI (never SI, BP).
%if BZ_BOXD != 20
 %error "bz_addbox lays a box record of 20 bytes = BZ_BOXD"
%endif
bz_addbox:
    mov di, [bz_c0n]
    cmp ax, di
    jge .x0
    mov ax, di
.x0:
    add di, [bz_W]
    dec di
    cmp bx, di
    jle .x1
    mov bx, di
.x1:
    sub bx, ax
    jl .out                     ; BX = w - 1
    mov di, [bz_wtop]           ; the window's top line
    cmp cx, di
    jge .y0
    mov cx, di
.y0:
    add di, BZ_LINES - 1
    cmp dx, di
    jle .y1
    mov dx, di
.y1:
    sub dx, cx
    jl .out                     ; DX = h - 1
    mov di, [bz_boxp]           ; the next record (bz_mkboxes starts it at
    stosw                       ; bz_boxes; 0 .. 3: a frame has at most four)
    xchg ax, cx
    stosw
    lea ax, [bx + 1]
    stosw
    xchg ax, dx
    inc ax
    stosw
    mov bx, [bz_nbox]
    inc bx
    mov [bz_nbox], bx
    shl bx, 1
    mov ax, [bz_bbtab - 2 + bx] ; ...and its buffer
    stosw
    xor ax, ax
    stosw                       ; no band
    mov al, [bz_grp]
    mov [di + 18 - 12], al
    add di, BZ_BOXD - 12
    mov [bz_boxp], di
.out:
    ret
bz_bbtab:
    dw bz_boxbuf, bz_boxbuf + BZ_BOXB, bz_boxbuf + 2 * BZ_BOXB, bz_boxbuf + 3 * BZ_BOXB

; -----------------------------------------------------------------------------
; bz_csplit - where this frame's entering column [bz_ccol] splits round the
; boxes (SPEC.md 128.2 rules 3 and 4, 128.11.10.3): bz_csp[i] = the column's
; rows that go before box i (non-decreasing), and CX = bz_csp[0], those before
; the first.  The column is written from the retrace and outruns the beam
; (~0.4k clocks a CGA row against 0.6k), but a whole column first would leave
; the boxes to start some 20-30k clocks after the retrace, with the beam
; already in the middle third where the camera keeps the ball, and the box
; writer is slower than the beam.  So the column's rows and the boxes go in
; RASTER ORDER: before each box (sorted by first line), the column's rows that
; end above its first line; after the last, the rest.  A FIRST box at window
; row 0 has no rows above it: then the column's rows down to that box's LAST
; line go first - they outrun the beam, the box does not - and bz_tb times it
; from line 0 ([bz_row0] = 1, SPEC.md 128.9 item 6).  A box that holds a cell
; of the column must follow ALL of it (the column would write the course over
; the ball), so then CX = H, the whole column first; with no box, too.  In
; steady state no box touches the column: the dead zone keeps the ball two
; words or more from either edge while the camera steps sideways.
; Clobbers AX, BX, DX, SI, DI.
; -----------------------------------------------------------------------------
bz_csplit:
    mov cx, [bz_nbox]
    jcxz .whole
    mov si, bz_boxes
.hold:
    mov ax, [bz_ccol]           ; the column inside [x0, x0 + w): the whole
    sub ax, [si]                ; column first (unsigned: left of x0 is huge)
    cmp ax, [si + 4]
    jb .whole
    add si, BZ_BOXD
    loop .hold
    mov si, bz_boxes
    mov di, bz_csp
    xor bx, bx                  ; BX = the last split
    mov dx, [bz_nbox]
    mov cl, [bz_lsh]
.box:
    mov ax, [si + 2]            ; the box's top row in the window
    sub ax, [bz_wtop]
    shr ax, cl
    cmp di, bz_csp
    jne .mono
    or ax, ax
    jnz .mono
    mov ax, [si + 2]            ; the first box at row 0: down to its last line
    add ax, [si + 6]
    dec ax
    sub ax, [bz_wtop]
    shr ax, cl
    inc ax
    mov byte [bz_row0], 1
.mono:
    cmp ax, bx
    jae .st
    mov ax, bx
.st:
    mov bx, ax
    mov [di], ax
    inc di
    inc di
    add si, BZ_BOXD
    dec dx
    jnz .box
    mov cx, [bz_csp]
    ret
.whole:
    mov cx, [bz_H]
    ret

; -----------------------------------------------------------------------------
; bz_rows - the entering ROWS (SPEC.md 128.2 rule 1), before the start address
; changes: moving down, the new window's bottom |dr| rows; moving up, its top
; ones - and of each only the cells NOT in an entering column (a diagonal
; step's corner belongs to the column).  Every such cell lies in the old
; window's slack.  The clock is sampled after each row.  Preserves nothing.
; -----------------------------------------------------------------------------
bz_rows:
    mov dx, [bz_dr]
    or dx, dx
    jz .out
    mov bx, [bz_c0n]            ; the columns
    mov cx, [bz_W]
    mov ax, [bz_dc]
    or ax, ax
    jz .rows
    dec cx                      ; one fewer: the column's
    or ax, ax
    jns .rows
    inc bx                      ; moving left: the column is the first
.rows:
    mov ax, [bz_R0n]
    or dx, dx
    js .up
    add ax, [bz_H]              ; moving down: the bottom dr rows
    sub ax, dx
    jmp .loop
.up:
    neg dx                      ; moving up: the top -dr rows
.loop:
    call bz_row
    call bz_clk_sample
    inc ax
    dec dx
    jnz .loop
.out:
    ret

; bz_fullw - THE FULL WRITE (SPEC.md 128.2): every window cell from the course,
; a row at a time, the clock sampled per row.  The start address went first
; (bz_tf); the picture assembles behind the BLANK (128.14.5.6): the card's
; video gated before the first row, lit again in the next frame's retrace
; (bz_tf's .col).  Preserves nothing.
bz_fullw:
    inc word [bz_nfull]
    call bz_blank
    mov ax, [bz_R0n]
    mov bx, [bz_c0n]
    mov cx, [bz_W]
    mov dx, [bz_H]
.row:
    call bz_row
    call bz_clk_sample
    inc ax
    dec dx
    jnz .row
    ret

; bz_blank, bz_unblank - the card's VIDEO gated across a full write (SPEC.md
; 128.14.5.6, O47): the mode control register gets the bracket mode's value
; less its video-enable bit (bit 3), then the value back - the kernel's own
; blank (vid_blank_kind) and on the Hercules its very bytes, 02h then 0Ah
; (graphics, page 0, video); on the CGA 22h then 2Ah, the IBM ROM's mode-4
; value.  bz_unblank does nothing unless bz_blank ran.  Preserve all but
; the flags.
bz_blank:
    push ax
    mov al, 22h
    mov byte [bz_blk], 1
    jmp short bz_unblank.out
bz_unblank:
    cmp byte [bz_blk], 0
    je .x
    push ax
    mov al, 2ah
    mov byte [bz_blk], 0
.out:
    push dx
    mov dx, 3d8h
    cmp byte [bz_herc], 0
    je .o
    mov dx, 3b8h
    sub al, 20h                 ; 02h, 0Ah
.o:
    out dx, al
    pop dx
    pop ax
.x:
    ret
