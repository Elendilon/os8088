; bzgame.inc - BONANZA's frame loop, simulation, camera, autopilot and
; instruments (SPEC.md 128.4 - 128.6).
;
; =============================================================================
; GUEST STATE A HARNESS READS (tests/bonanza_*.py; offsets are the package
; segment's, resolved through the listing or a re-assembly like Excitebike's)
; =============================================================================
;   bz_mode     byte   0 play, 1 benchmark (B), 2 replay (R, SPEC.md 128.11.12)
;   bz_fs       byte   1 while the bracket is up (mode set .. the loop's end)
;   bz_err      byte   0; 1 the mode was refused; 2 the display changed under us
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
;                      k (0, 1), 68 + k shatter k (0 - 3) (bz_sprite); copy py & 1
;                      of a squash or shatter entry, at shift px & 3
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
;   bz_acc      6 DWORDS, PIT counts summed over the measured frames, one per
;                      part: 0 sim+camera (bz_t0..bz_ts), 1 box compose and the
;                      occluder pass (..bz_tr), 2 rows (..bz_tv), 3 retrace wait,
;                      IDLE (..bz_tf), 4 flip + columns (..bz_tb, and every run of
;                      column rows written after a box), 5 box write (bz_tb ..
;                      bz_presented less those runs).  CPU clocks = counts x 4.
;   bz_cmode    byte   the camera MODE (SPEC.md 128.11.11.1): 0 GLIDE, 1 TRICKLE
;                      (FOLLOW is gone).  C toggles it, in play and on the desktop;
;                      it persists across plays (bss, never reset).  The benchmark
;                      runs GLIDE whatever it says and leaves it alone
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
;   bz_res      byte   1 = the bz_r* copy below holds a finished benchmark
;   bz_rframes, bz_rmfr, bz_rncol, bz_rnrow, bz_rnfull, bz_rmiss, bz_rfmax,
;                      bz_racc, bz_rlate, bz_rnocf, bz_rnlay, bz_rn2bx, bz_rn3bx,
;                      bz_rnshd: that copy, the same layout as bz_frames .. bz_nshd
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
;   bz_t0 .. bz_ts .. bz_tr .. bz_tv .. bz_tf .. bz_tb [.. bz_tc] ..
;   bz_presented
; and bz_col / bz_row (bzvideo.inc) are the writers' entries.  The boxes are
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
BZ_NPART    equ 6               ; the frame's measured parts (the marks' gaps)
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
BZ_KSC_R    equ 13h             ; ...and R's: the replay (SPEC.md 128.11.12.2)
BZ_CMODES   equ 2               ; GLIDE, TRICKLE (SPEC.md 128.11.11.1)
; GLIDE's "faster than 4 px (x) / 2 lines (y) a FRAME" is the ball's TRAVEL
; over the last FOUR frames (SPEC.md 128.11.11.1), in the 24.8 low words of
; bz_bx, bz_by: rate-proof, where wave 1's |v| against a per-card constant
; assumed the full refresh.  bbcourse.Glide (GLIDE_FX, GLIDE_FY) is the model.
BZ_GTRX     equ 4 * 4 * 256     ; 4 px a frame, four frames
BZ_GTRY     equ 4 * 2 * 256     ; 2 lines a frame
BZ_K_L      equ 1               ; bz_keys: the arrows held
BZ_K_R      equ 2
BZ_K_U      equ 4
BZ_K_D      equ 8
BZ_LIVE     equ 52              ; bytes of bz_frames .. bz_nshd (the results copy)
BZ_SPR_SQ   equ 64              ; bz_spr: squash k is 64 + k ...
BZ_SPR_SHA  equ 68              ; ...and shatter k 68 + k (roll frames 0 - 63)

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
VAR bz_lsh,1
VAR bz_row0,1                   ; 1: this frame's box is at window row 0 (bz_csplit)
VAR bz_r0p,1                    ; 1: a box starts at the new window's first line
                                ; (bz_r0pend): bz_vr shuts interrupts at the rise
VAR bz_vedge,1                  ; 1: bz_vr saw the sync RISE (not already high)
VAR bz_crs,1                    ; the course K: BZ_CRS_FIRST to play, BZ_CRS_BENCH
                                ; for the benchmark (bzcourse.inc)
VAR bz_mapsh,1                  ; the course's MAPSH (bz_crshdr): 4 or 5
VAR bz_pad0,1                   ; (the words below stay even)
VAR bz_cmode,1                  ; the camera mode: 0 GLIDE, 1 TRICKLE
VAR bz_cuse,1                   ; ...the one this frame used (a benchmark: GLIDE)
VAR bz_ckey,1                   ; FFh while C was down last frame (the edge)
VAR bz_gpx,1                    ; GLIDE: 1 while the x pan is on
VAR bz_gpy,1                    ; ...the y pan
VAR bz_gpar,1                   ; ...the x pan's frame parity (0: step now)
VAR bz_gdx,1                    ; ...the ball's last x direction: 0 right, 1 left
VAR bz_gdy,1                    ; ...and y: 0 down, 1 up
VAR bz_gfast,2                  ; ...1 while the ball is FAST across (+0), down
                                ; (+1): its travel over four frames (128.11.11.1)
VAR bz_tri,1                    ; ...the travel ring's index (mod 4), and
VAR bz_pad1,1
VAR bz_trx,8                    ; the ring: the low words of bz_bx and bz_by at
VAR bz_try,8                    ; the end of each of the last four frames
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
VAR bz_hold,1                   ; 1: the old footprints are this frame's (bz_mkboxes)
VAR bz_ogate,1                  ; 1: the occluder pass runs this frame
VAR bz_grp,1                    ; bz_addbox: the box's group (0 the ball's)
; the replay log's recorder and player (SPEC.md 128.11.12)
VAR bz_rptr,2                   ; the next run's pair in bz_rlog
VAR bz_rruns,2                  ; a replay: the runs not yet read
VAR bz_rtrs,4                   ; the steps recorded, when TRUNCATED
VAR bz_rk,1                     ; the current run: its key byte, its count (a
VAR bz_rn,1                     ; replay: the count left)
VAR bz_rtr,1                    ; 1: the log is TRUNCATED, nothing more recorded
VAR bz_pad2,1
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
VAR bz_tos,2
; the clock
VAR bz_subs,2
VAR bz_pitl,2
VAR bz_msubs,2
VAR bz_mpit,2
VAR bz_lsubs,2
VAR bz_fper,4
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
VAR bz_bseg,2
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
VAR bz_csp,8                    ; ...before each box (bz_csplit)
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
VAR bz_boxes,4 * BZ_BOXD
VAR bz_boxbuf,4 * BZ_BOXB          ; four box buffers (SPEC.md 128.11.10.1),
                                ; whose first 512 bytes hold BZ_HTAB at a
                                ; Hercules launch, before the bracket (128.11.3)
%if bz_rframes - bz_frames != BZ_LIVE || bz_sox0 != bz_ofx0 + 8 || bz_snx0 != bz_nfx0 + 8 || bz_nfx0 != bz_sox0 + 8
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
; accumulator (bz_acc + BX) and to the frame's period (bz_fper) when this
; frame is measured, and the mark becomes the base.  A mark costs ~1.0k clocks
; of its own on MartyPC's 8088 (a PIT latch, ~0.2k, and the 32-bit sums;
; measured: a frame with no rows still shows ~1.07k in the rows part), billed
; to the part it closes: the small parts' means read that much high, and a
; benchmark's busy time ~4-5k above play's, where the sums are skipped.  Preserves all but the flags.
; -----------------------------------------------------------------------------
bz_mark:
    push ax
    push cx
    push dx
    call bz_clk_sample
    cmp byte [bz_meas], 0
    je .base
    mov ax, [bz_subs]
    sub ax, [bz_msubs]
    xor dx, dx                  ; DX:AX = whole sub-ticks in counts: 0 on most
    or ax, ax                   ; marks and 1 on most of the rest, neither of
    jz .ph                      ; which needs the MUL
    cmp ax, 1
    jne .mul
    mov ax, BZ_SUB
    jmp .ph
.mul:
    mov cx, BZ_SUB
    mul cx
.ph:
    mov cx, [bz_mpit]
    sub cx, [bz_pitl]           ; + the phase moved (signed: the count runs down)
    add ax, cx
    adc dx, 0
    test ch, 80h
    jz .pos
    dec dx
.pos:
    add [bz_acc + bx], ax
    adc [bz_acc + bx + 2], dx
    add [bz_fper], ax           ; ...and to this frame's period
    adc [bz_fper + 2], dx
.base:
    mov ax, [bz_subs]
    mov [bz_msubs], ax
    mov ax, [bz_pitl]
    mov [bz_mpit], ax
    pop dx
    pop cx
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
bz_latechk:
    push ax
    push bx
    push cx
    push dx
    cmp byte [bz_vedge], 0
    je .lv
    add ax, 16                  ; the sync's lines (less BZ_VLAT, below)
.lv:
    mov bx, ax
    mov cl, 6
    shl ax, cl                  ; 64 n
    cmp byte [bz_herc], 0
    jne .h
    mov cx, bx
    shl bx, 1
    add bx, cx
    shl bx, 1
    shl bx, 1                   ; 12 n
    add ax, bx                  ; 76 n: CGA lines
    jmp short .b
.h:
    sub ax, bx                  ; 63 n: Hercules lines
.b:
    add ax, [bz_lblank]
    cmp byte [bz_vedge], 0
    je .lb
    sub ax, BZ_VLAT             ; the sample came up to BZ_VLAT after the rise
.lb:
    mov bx, ax                  ; BX = the counts the beam takes to get there
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
    pop cx
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
    mov [bz_fper], ax
    mov [bz_fper + 2], ax
    mov [bz_keys], al
    mov [bz_oldv], al
    mov [bz_meas], al
    mov [bz_fin], al            ; the face's "Finished" goes with a new play
    mov [bz_rn], al             ; the log: no current run, from its first pair
    mov word [bz_rptr], bz_rlog + BZR_RUNS
    mov di, bz_frames
    mov cx, BZ_LIVE / 2
    rep stosw
    mov word [bz_wp], 1         ; waypoint 0 is the start
    mov byte [bz_first], 1
    mov byte [bz_ckey], 0ffh    ; C must go down IN play to count (an edge)
    mov al, [bz_mode]
    cmp al, 1
    jb .rec
    ja .rep
    mov byte [bz_res], 0        ; a benchmark replaces the last one's results
    jmp short .play             ; (and leaves the log alone)
.rep:
    mov ax, [bz_rlog + BZR_NRUN] ; a replay: the log's runs, none read yet
    mov [bz_rruns], ax
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
    cmp byte [bz_goal], 0       ; the frame after the step whose centre is on
    je .live                    ; a GOAL cell, in play or a replay: the run is
    mov byte [bz_fin], 1        ; over (SPEC.md 128.10.6.2), and the face says
    jmp short .out              ; how long it took
.live:
    cmp byte [bz_mode], 2       ; a replay's end: the frame after its last
    jne .on                     ; recorded step (SPEC.md 128.11.12.2)
    call bz_rleft
    jnz .on
.out:
    cmp byte [bz_mode], 0       ; a play's log closed: its last run, its
    jne .ret                    ; steps, COMPLETE
    call bz_rfin
.ret:
    ret
.on:
    cmp byte [bz_mode], 0
    jne .steps
    call bz_input               ; play: the keys, once a frame
.steps:
    mov byte [bz_resp], 0       ; (a respawn in this frame's steps: the cut)
    mov cx, [bz_subs]           ; (sampled at the last frame's end mark)
    sub cx, [bz_lsubs]
    add [bz_lsubs], cx
    cmp cx, BZ_STEPS
    jbe .n
    mov cx, BZ_STEPS
.n:
    jcxz .camera
.step:
    cmp byte [bz_mode], 2       ; a replay steps while its log lasts
    jne .stp
    call bz_rleft
    jz .camera
.stp:
    call bz_step
    cmp byte [bz_goal], 0       ; the GOAL step is a play's last: a replay of
    jne .camera                 ; its log ends on the same step (128.11.12.2)
    loop .step
.camera:
    call bz_camera
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
bz_tr:                          ; into every box (SPEC.md 128.11.10.2)
    mov bx, 1 * 4
    call bz_mark
    cmp byte [bz_full], 0
    jne bz_tv
    call bz_rows
bz_tv:
    mov bx, 2 * 4
    call bz_mark
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
    jmp short bz_tb
.col:
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
    jbe bz_presented
bz_tc:
    call bz_mark                ; BX = 5*4: the box write ends here
    mov ax, [bz_ccol]
    mov bx, [bz_cdone]
    call bz_col
    mov bx, 4 * 4               ; ...which are the flip+columns part's
bz_presented:
    call bz_mark
    cmp byte [bz_disc], 0       ; a CENTRED full write (the first frame, a
    je .kept                    ; cut): its elapsed sub-ticks are DISCARDED,
    mov byte [bz_disc], 0       ; so the ball just put at rest is not caught up
    mov ax, [bz_subs]           ; with 8 steps (SPEC.md 128.10.8 item 3)
    mov [bz_lsubs], ax
.kept:
    inc word [bz_frames]
    cmp byte [bz_meas], 0
    je .fper
    inc word [bz_mfr]
    mov ax, [bz_fper]           ; this frame's period, PIT counts: the worst...
    mov dx, [bz_fper + 2]
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
    xor ax, ax
    mov [bz_fper], ax
    mov [bz_fper + 2], ax
    push ds                     ; the footprints drawn are the next frame's old
    pop es                      ; ones: the ball's and the shadow's rects, and
    mov si, bz_nfx0             ; whether the shadow was drawn
    mov di, bz_ofx0
    mov cx, 8
    rep movsw
    mov al, [bz_snv]
    mov [bz_sov], al
    mov byte [bz_oldv], 1
    cmp byte [bz_mode], 1
    jne .next
    cmp word [bz_frames], BZ_BENCH
    jb .next
    mov si, bz_frames           ; the benchmark is done: its results stay for
    mov di, bz_rframes          ; the desktop
    mov cx, BZ_LIVE / 2
    rep movsw
    mov byte [bz_res], 1
    ret
.next:
    jmp bz_t0

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
; bz_rrec - BL = this step's key byte, which does not extend the current run
; (another byte, or the run at 255): the run is FLUSHED and BL starts the next
; - unless the buffer is then full, when the log is TRUNCATED: flags bit 1,
; the steps so far kept in bz_rtrs, and nothing more recorded (bz_rk = FFh, a
; byte no step has, sends every later step here, where bz_rtr stops it).
; Clobbers AX, DX, DI.
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
    mov byte [bz_rn], 1
.out:
    ret

; bz_rstore - the current run (bz_rk, bz_rn), if it has a step, stored at
; bz_rptr as a pair and counted.  Clobbers AX, DI.
bz_rstore:
    mov ah, [bz_rn]
    or ah, ah
    jz .out
    mov al, [bz_rk]
    mov di, [bz_rptr]
    mov [di], ax
    inc di
    inc di
    mov [bz_rptr], di
    inc word [bz_rlog + BZR_NRUN]
    mov byte [bz_rn], 0
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
    ret

; bz_rleft - a replay: ZF = 1 when the log is spent (no step left in the
; current run and no run left to read).  Clobbers AX.
bz_rleft:
    mov al, [bz_rn]
    or al, [bz_rruns]
    or al, [bz_rruns + 1]
    ret

; bz_rnext - a replay's next key byte -> BL: from the current run, or the next
; pair once it is spent.  The log is the package's own, written by bz_rrec:
; trusted, and decoded without a check (SPEC.md 128.11.12.2).  bz_play's step
; loop asks bz_rleft first.  Clobbers AX, SI.
bz_rnext:
    cmp byte [bz_rn], 0
    jne .cur
    mov si, [bz_rptr]
    lodsw                       ; AL the key byte, AH its count (1 - 255)
    mov [bz_rptr], si
    dec word [bz_rruns]
    mov [bz_rk], al
    mov [bz_rn], ah
.cur:
    dec byte [bz_rn]
    mov bl, [bz_rk]
    ret

; -----------------------------------------------------------------------------
; the keys.  bz_exitchk: CF = 1 leave (Alt+Enter, Esc, F); every typed key is
; drained so none leaks to the desktop (WireBall's rule).  Clobbers AX.
; -----------------------------------------------------------------------------
bz_exitchk:
    call os88alt_edge
    jc .leave
    mov al, KSC_ESC
    call OSAPI_KEY_DOWN
    jc .leave
.drain:
    mov ah, 1
    int 16h
    jz .stay
    xor ah, ah
    int 16h
    cmp al, 27
    je .leave
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
    mov al, BZ_KSC_C
    call OSAPI_KEY_DOWN
    sbb bl, bl                  ; BL = FFh while C is down
    mov al, bl
    xchg al, [bz_ckey]          ; AL = last frame's
    not al
    and al, bl                  ; down now and not then: the edge
    jz .arrows
    call bz_cnext
.arrows:
    xor bl, bl
    mov al, KSC_LEFT
    call OSAPI_KEY_DOWN
    jnc .r
    or bl, BZ_K_L
.r:
    mov al, KSC_RIGHT
    call OSAPI_KEY_DOWN
    jnc .u
    or bl, BZ_K_R
.u:
    mov al, KSC_UP
    call OSAPI_KEY_DOWN
    jnc .d
    or bl, BZ_K_U
.d:
    mov al, KSC_DOWN
    call OSAPI_KEY_DOWN
    jnc .sp
    or bl, BZ_K_D
.sp:
    mov al, KSC_SPACE
    call OSAPI_KEY_DOWN
    jnc .sh
    or bl, BZ_K_HOP
.sh:
    mov ah, 2                   ; the BIOS's shift flags: bit 1 Left Shift
    int 16h
    test al, 2
    jz .out
    or bl, BZ_K_GRIP
.out:
    mov [bz_keys], bl
    pop bx
    pop ax
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
; bz_camera - the ball's integer position, its sprite and shadow (bz_sprite),
; then the new window.  Runs ONCE A FRAME, after the frame's steps (SPEC.md
; 128.9: the camera is part of the simulation, and its cadence is the frame
; rate's).  The first frame centres the window on the ball and is a FULL WRITE,
; as is any step past BZ_MAXR/BZ_MAXC.  After it, the MODE (bz_cmode; GLIDE in
; a benchmark, SPEC.md 128.11.11.1):
;
;   GLIDE   (bz_camglide) rests while the ball is inside the dead zone and the
;           band, and PANS when it leaves them, ahead of the ball, until the
;           target is reached: the camera either rests or moves fast
;   TRICKLE wave 0's camera, unchanged (SPEC.md 128.5): the "classic" one
;
; Both keep the ball's centre inside the dead zone (the window's middle half
; across) and the band (its middle third down) wherever the course lets the
; window go, at most BZ_MAXR rows and BZ_MAXC columns a frame, clamped to the
; course - so 128.2 rule 4's column split is the same in both.  GLIDE's "fast"
; is the ball's travel over the last four frames, kept in every mode (the
; ring bz_trx, bz_try: SPEC.md 128.11.11.1, bbcourse.Glide's).
; Sets bz_sb, bz_px, bz_py, the sprite's state, bz_R0n, bz_c0n, bz_dr, bz_dc,
; bz_full, bz_meas, bz_cuse.  Preserves nothing.
; -----------------------------------------------------------------------------
bz_camera:
    mov ax, [bz_gx + 1]         ; the ball's cell row s_b, once a frame (the
    mov dx, [bz_gy + 1]         ; idle test's and the occluders', 128.10.8)
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
    mov al, [bz_cmode]          ; the mode this frame: the benchmark's is GLIDE
    cmp byte [bz_mode], 1       ; whatever the player chose, so its route and
    jne .muse                   ; its numbers stay comparable (bz_cmode is
    xor al, al                  ; left as it was)
.muse:
    mov [bz_cuse], al
    cmp byte [bz_resp], 0       ; THE CUT (SPEC.md 128.10.8 item 3): a frame
    je .nocut                   ; whose steps respawned the ball where its
    call bz_outwin              ; footprint is not wholly inside the window
    jnc .nocut                  ; is the first frame's centred full write
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
    xor ax, ax                  ; every mode starts at rest, heading right
    mov [bz_gpx], ax            ; and down (bz_gpx, bz_gpy; bz_gpar, bz_gdx)
    mov [bz_gpar], ax
    mov [bz_gdy], al
    mov ax, [bz_bx]             ; the travel ring filled with the present
    mov dx, [bz_by]             ; position: at rest
    mov bx, 6
.tf:
    mov [bz_trx + bx], ax
    mov [bz_try + bx], dx
    dec bx
    dec bx
    jns .tf
    jmp .decided
.modes:
    ; --- the travel over four frames (SPEC.md 128.11.11.1): read the slot
    ; written four frames ago, then write the present into it, step the index
    mov bl, [bz_tri]
    xor bh, bh
    shl bx, 1
    xor si, si                  ; SI: low byte fast across, high byte down
    mov ax, [bz_bx]
    mov dx, ax
    xchg ax, [bz_trx + bx]
    sub dx, ax
    call bz_abs
    cmp dx, BZ_GTRX
    jbe .ty
    inc si
.ty:
    mov ax, [bz_by]
    mov dx, ax
    xchg ax, [bz_try + bx]
    sub dx, ax
    call bz_abs
    cmp dx, BZ_GTRY
    jbe .tr
    add si, 100h
.tr:
    mov [bz_gfast], si
    inc byte [bz_tri]
    and byte [bz_tri], 3
    cmp byte [bz_cuse], 0
    jne .trickle
    call bz_camglide
    jmp .moved
.trickle:
    ; --- TRICKLE, wave 0's camera (SPEC.md 128.5) ---
    mov word [bz_gpx], 0        ; (GLIDE's pans are off outside GLIDE)
    ; vertical: the band [T + 1/3, T + 2/3] of the window's lines
    mov ax, [bz_py]
    add ax, 8                   ; the ball's centre line
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
    and al, [bz_mode]           ; since nothing reads it (bz_mode 1, 0 or 2:
                                ; only the benchmark's keeps the bit)
    mov [bz_meas], al
    ret

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
;         bz_gh's floor); else the roll frame
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
    jz .roll
    cmp byte [bz_air], 0        ; at its floor: grounded, or airborne over the
    je .sqf                     ; floor at its whole z or below
    cmp byte [bz_ghv], 0
    je .roll
    mov dx, [bz_gh]
    sar dx, 1
    sar dx, 1
    cmp [bz_gz + 1], dx
    jg .roll
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
; bz_camglide - GLIDE (SPEC.md 128.9), the default: the camera RESTS, or it
; PANS fast; it never trickles.  CL = [bz_lsh].  Sets [bz_c0n], [bz_R0n].
;
; ACROSS: at rest until the ball's centre leaves the dead zone [2W, 6W] px of
; the window (its middle half, 128.5's).  Then a pan toward the column that
; puts the ball on the dead zone's TRAILING edge - a quarter-window behind the
; centre, so the camera sees a quarter-window AHEAD of it in its direction of
; travel (the direction is the sign of bz_vx; at rest, the last one) - which
; is re-aimed every frame and ends where the target is reached.  The target
; is rounded so the ball lands INSIDE the edge (floor right, ceiling left), and
; clamped to the course: a pan the course stops ends.  A pan steps one column
; every SECOND frame (8 px in two: 4 px a frame), and every frame while the
; ball is faster than 4 px a frame (bz_gfast: its travel over the last four
; frames, SPEC.md 128.11.11.1, bz_camera's ring), or while the ball is still
; outside the dead zone (the first frame of a pan, so the edge holds).
;
; DOWN: the same on rows: at rest inside the band [L/3, 2L/3] (the middle
; third of BZ_LINES lines, 66 .. 133), and when the ball leaves it a pan to
; the row that puts it on the band's trailing edge - a sixth of the window
; behind the centre, so the camera leads by a sixth - at one row a frame, two
; while the ball is faster than 2 lines a frame (bz_gfast + 1), and a second one
; while the first still leaves the ball outside the band.
;
; (The SPEC's "the ball a quarter-window / a sixth AHEAD of the centre" is the
; camera's lead: putting the BALL ahead of the centre would aim at the edge it
; just crossed, and the pan would be wave 0's trickle again.)
; -----------------------------------------------------------------------------
bz_camglide:
    ; ---- across ----
    mov si, [bz_c0]
    mov ax, [bz_vx]             ; the direction of travel
    or ax, ax
    jz .xdir
    mov byte [bz_gdx], 0
    jns .xdir
    mov byte [bz_gdx], 1
.xdir:
    mov bx, [bz_W]
    shl bx, 1                   ; BX = 2W, the dead zone's left edge
    mov di, bx
    shl di, 1
    add di, bx                  ; DI = 6W, its right edge
    mov ax, [bz_px]
    add ax, 8                   ; AX = the ball's centre px
    mov dx, si
    shl dx, 1
    shl dx, 1
    shl dx, 1
    neg dx
    add dx, ax                  ; DX = ...in the window
    xor ch, ch                  ; CH = 1: the ball is outside the dead zone
    cmp dx, bx
    jl .xout
    cmp dx, di
    jle .xin
.xout:
    inc ch
    cmp byte [bz_gpx], 0
    jne .xin
    mov byte [bz_gpx], 1        ; a pan begins: its first column now
    mov byte [bz_gpar], 0
.xin:
    cmp byte [bz_gpx], 0
    je .xdone
    cmp byte [bz_gdx], 0        ; the target column: the ball on the
    jne .xtl                    ; trailing edge
    sub ax, bx                  ; right: floor((centre - 2W) / 8)
    jge .xtr
    xor ax, ax
.xtr:
    shr ax, 1
    shr ax, 1
    shr ax, 1
    jmp .xtc
.xtl:
    sub ax, di                  ; left: ceiling((centre - 6W) / 8)
    jg .xtl2
    xor ax, ax
    jmp .xtc
.xtl2:
    add ax, 7
    shr ax, 1
    shr ax, 1
    shr ax, 1
.xtc:
    cmp ax, [bz_cmax]
    jle .xtm
    mov ax, [bz_cmax]
.xtm:
    cmp ax, si                  ; AX = the target
    je .xrest
    mov dl, [bz_gpar]
    xor byte [bz_gpar], 1
    or ch, ch                   ; outside the dead zone: now
    jnz .xstep
    or dl, dl                   ; ...every second frame
    jz .xstep
    cmp byte [bz_gfast], 0      ; ...every frame while the ball is fast
    je .xdone
.xstep:
    cmp ax, si
    jl .xleft
    inc si
    jmp .xreach
.xleft:
    dec si
.xreach:
    cmp ax, si
    jne .xdone
.xrest:
    mov byte [bz_gpx], 0
.xdone:
    mov [bz_c0n], si
    ; ---- down ----
    mov si, [bz_R0]
    mov ax, [bz_vy]
    or ax, ax
    jz .ydir
    mov byte [bz_gdy], 0
    jns .ydir
    mov byte [bz_gdy], 1
.ydir:
    mov ax, [bz_py]
    add ax, 8                   ; AX = the ball's centre line
    mov dx, si
    shl dx, cl
    neg dx
    add dx, ax                  ; DX = ...in the window
    cmp dx, BZ_LINES / 3
    jl .yout
    cmp dx, 2 * BZ_LINES / 3
    jle .yin
.yout:
    mov byte [bz_gpy], 1
.yin:
    cmp byte [bz_gpy], 0
    je .ydone
    cmp byte [bz_gdy], 0        ; the target row: the ball on the trailing edge
    jne .ytu
    sub ax, BZ_LINES / 3        ; down: floor((centre - L/3) / rl)
    jge .ytd
    xor ax, ax
.ytd:
    shr ax, cl
    jmp .ytc
.ytu:
    sub ax, 2 * BZ_LINES / 3    ; up: ceiling((centre - 2L/3) / rl)
    jg .ytu2
    xor ax, ax
    jmp .ytc
.ytu2:
    add ax, [bz_rl]
    dec ax
    shr ax, cl
.ytc:
    cmp ax, [bz_rmax]
    jle .ytm
    mov ax, [bz_rmax]
.ytm:
    cmp ax, si                  ; AX = the target
    je .yrest
    mov di, 1                   ; DI = the step, toward the target
    jg .ys
    neg di
.ys:
    add si, di                  ; one row
    cmp ax, si
    je .yrest
    cmp byte [bz_gfast + 1], 0  ; two while the ball is fast...
    jne .y2
    mov dx, [bz_py]             ; ...or while one leaves it outside the band
    add dx, 8
    mov bx, si
    shl bx, cl
    sub dx, bx
    cmp dx, BZ_LINES / 3
    jl .y2
    cmp dx, 2 * BZ_LINES / 3
    jle .ydone
.y2:
    add si, di
    cmp ax, si
    jne .ydone
.yrest:
    mov byte [bz_gpy], 0
.ydone:
    mov [bz_R0n], si
    ret

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
bz_mkboxes:
    push ds
    pop es
    mov ax, [bz_R0n]            ; the new window's top line (the clip, the
    mov cl, [bz_lsh]            ; pass, the column's split, the lateness)
    shl ax, cl
    mov [bz_wtop], ax
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
    mov word [bz_nbox], 0
    mov byte [bz_hold], 0       ; the old footprints count unless a full write
    cmp byte [bz_full], 0       ; or the first frame
    jne .go
    cmp byte [bz_oldv], 0
    je .go
    mov byte [bz_hold], 1
    or bp, bp
    jnz .go
    ret                         ; idle: nothing to compose or write
.go:
    mov al, [bz_shc]
    mov [bz_snv], al
.groups:
    mov di, bz_gr               ; DI = the next rect
    ; THE BALL GROUP: the union of the old and the new, or each
    mov si, bz_nfx0
    cmp byte [bz_hold], 0
    je .bput
    mov bx, bz_ofx0
    call bz_union
    jnc .bu
    mov si, bz_ofx0
    call bz_rput
    mov si, bz_nfx0
    jmp short .bput
.bu:
    mov si, bz_ur
.bput:
    call bz_rput
    mov dx, di                  ; DX = the shadow group's first rect
    ; THE SHADOW GROUP: the old (drawn last frame) and the new (drawn now)
    cmp byte [bz_hold], 0
    je .sn
    cmp byte [bz_sov], 0
    je .sn
    mov si, bz_sox0
    cmp byte [bz_snv], 0
    je .sput                    ; the old alone: its restoring box
    mov bx, bz_snx0
    call bz_union
    jnc .su
    call bz_rput                ; two: the old, then the new
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
    call bz_rput
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
    call bz_rput                ; (DX = bz_gr + 8: the one rect is group 0)
    jmp short .emit
.split:
    cmp byte [bz_ogate], 0      ; the pass runs and the shadow is not in the
    je .emit                    ; ball's box: not drawn this frame
    cmp byte [bz_snv], 0
    je .emit
    mov byte [bz_snv], 0
    jmp .groups
.emit:
    ; the rects as boxes, each clipped to the new window: group 0 the ball's
    mov si, bz_gr
.e:
    cmp si, di
    jae .sort
    xor al, al
    cmp si, dx
    jb .g
    inc ax
.g:
    mov [bz_grp], al
    push si
    push di
    push dx
    mov ax, [si]
    mov bx, [si + 2]
    mov cx, [si + 4]
    mov dx, [si + 6]
    call bz_addbox
    pop dx
    pop di
    pop si
    add si, 8
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
    push cx
    mov cx, BZ_BOXD / 2
    mov di, si
.swap:
    mov ax, [di]
    xchg ax, [di + BZ_BOXD]
    mov [di], ax
    inc di
    inc di
    loop .swap
    pop cx
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
; does not fit one box (BZ_BOXW words x BZ_BOXH lines).  Clobbers AX.
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
    cmp ax, BZ_BOXH             ; CF = it fits (h - 1 < BZ_BOXH) ...
    cmc                         ; ...turned round
    ret
.no:
    stc
    ret

; bz_rput - the rect at SI copied to DI, DI past it.  ES = ours.  Clobbers CX.
bz_rput:
    push si
    mov cx, 4
    rep movsw
    pop si
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
; Clobbers AX-DX, SI, DI (never BP).
%if BZ_BOXD != 20
 %error "bz_addbox scales the box index by 20 = BZ_BOXD"
%endif
bz_addbox:
    cmp ax, [bz_c0n]
    jge .x0
    mov ax, [bz_c0n]
.x0:
    mov si, [bz_c0n]
    add si, [bz_W]
    dec si
    cmp bx, si
    jle .x1
    mov bx, si
.x1:
    sub bx, ax
    jl .out                     ; BX = w - 1
    mov si, [bz_wtop]           ; the window's top line
    cmp cx, si
    jge .y0
    mov cx, si
.y0:
    add si, BZ_LINES - 1
    cmp dx, si
    jle .y1
    mov dx, si
.y1:
    sub dx, cx
    jl .out                     ; DX = h - 1
    mov di, [bz_nbox]           ; 0 .. 3: a frame has at most four boxes
    shl di, 1
    mov si, di
    shl si, 1
    shl si, 1
    add si, di
    shl si, 1                   ; x BZ_BOXD (20)
    add si, bz_boxes
    mov di, [bz_bbtab + di]     ; ...and its buffer
    mov [si], ax
    mov [si + 2], cx
    inc bx
    mov [si + 4], bx
    inc dx
    mov [si + 6], dx
    mov [si + 8], di
    xor ax, ax
    mov [si + 10], ax           ; no band
    mov al, [bz_grp]
    mov [si + 18], al
    inc word [bz_nbox]
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
; (bz_tf); the picture assembles in view.  Preserves nothing.
bz_fullw:
    inc word [bz_nfull]
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
