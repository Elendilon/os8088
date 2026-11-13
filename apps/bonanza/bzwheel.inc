; bzwheel.inc - BONANZA's LANES and its WHEEL (SPEC.md 128.12.4, 128.12.5,
; 128.12.7's bz_heavy, 128.12.15), wave 3.  The wheel is ADAPTED from TITHE's
; pacing wheel (branch tithe-new, its SPEC.md 125.5 and apps/tithe/tithe.asm:
; ti_frame, ti_credit, ti_calibrate, ti_overran); nothing of it is %included.
;
; A LANE is a rectangle of the course's block MAP (at most 4 words x 3 block
; rows) whose POSES are sets of map words, in the course part after the grid
; (the prop table, SPEC.md 128.12.3.1: the records with a lane come first,
; sorted by first block row, so lane i is record i).  The MAP HOLDS THE DRAWN
; POSE (bz_ldrw): a commit copies a pose's words into the map through the
; course part's own segment - its selector on kern_mega, nothing through CS,
; no segment arithmetic - and every writer that reads the map (rows, columns,
; boxes, the occluder pass's lay) draws that pose with no change of its own.
; A pose reaches the glass four ways (128.12.4.2): a WHEEL commit in the
; retrace wait's time, the LEAD after the flip, the CONTACT box, and an
; ENTERING strip.
;
; =============================================================================
; GUEST STATE A HARNESS READS (beside bzgame.inc's head)
; =============================================================================
;   bz_hold     byte   a harness's: the next frame's bz_t0 spins bz_hold x 256
;                      PIT counts before its steps, then clears it (a late
;                      frame on demand, bonanzawheel)
;   bz_hvoff    byte   a harness's: 1 forces bz_heavy to 0 (wave 2's camera,
;                      the BENCH A/B, SPEC.md 128.12.9)
;   bz_heavy    byte   this frame's level (128.12.7): 2 a contact group, 1 the
;                      pass / two ball boxes / the slab near an edge, 0
;   bz_hedr,bz_hedc byte the edge clause: the ball's new footprint near the top
;                      or bottom (releases the rows), the left or right (the
;                      column), the window as it stood before the camera
;   bz_ctype    byte   the contact group: 0 none, 1 a lane (bz_cln), 2 the slab
;   bz_crect    4 words its rect, words x lines inclusive (x0 x1 y0 y1)
;   bz_ldrw     16 bytes each lane's DRAWN pose: the map's (display state, never
;                      read by physics);  bz_lage 16 bytes the frames each has
;                      been due while shown;  bz_ltru 16 bytes its TRUE pose,
;                      as the walk last computed it
;   bz_lr0,bz_lr1 byte the walk's slice [lr0, lr1) of the lanes
;   bz_wcn      byte   this frame's wheel candidates, bz_wcl their lanes in
;                      raster order (bit 7 set once committed)
;   bz_wld      byte   the lane (+ 1) the last wheel marked for the LEAD
;   bz_wcal     byte   1 once this launch's calibration ran
;   bz_wlw,bz_wll,bz_warr word the calibration (SPEC.md 128.12.5.4): a word-line
;                      and a line in 1/16 PIT counts, the commit's fixed part
;                      in counts;  bz_cT 3 words its means T1, T3, T3n
;   bz_trim     word   the trim, 30 - 100 (cost' = cost x 100 / trim)
;   bz_pline    word   the platform's DRAWN line (8000h: not on the card),
;                      bz_ptru its true one this frame
;   the counters are bzgame.inc's (bz_wcom .. bz_wtmin, in the results copy)
; =============================================================================

BZ_WMARG    equ 1600            ; PIT counts: what runs between a commit's closing
                                ; latch and bz_vr's first read, at most (SPEC.md
                                ; 128.12.5.3's table, PROVISIONAL, O26)
BZ_WGRD     equ 2               ; the beam guard, lines
BZ_WLAG     equ 8               ; frames due and shown before bz_wlate counts it
BZ_WPRO     equ 3               ; frames a WHEEL candidate waits before it takes
                                ; the contact slot on a frame that allows a
                                ; contact lane, BZ_WPRF on any frame (the final
BZ_WPRF     equ 5               ; pass: MILL's heavy frames starve the wait)
BZ_TRIMMIN  equ 30              ; TITHE's trim: the floor, ...
BZ_TRIMDN   equ 12              ; ...the fall on an overrun (a fit adds 1)
BZ_HEDGE    equ 16              ; the edge clause's zone, lines (and 24 px across)
BZ_CALN     equ 8               ; the calibration's samples a size
BZ_PWHEEL   equ 6               ; the wheel's part (bz_tw .. bz_tv), appended
BZ_WKN      equ 7               ; bz_vinit's per-card words, bz_wb0 .. bz_warr
BZ_PLNONE   equ 8000h           ; bz_pline: the slab is not on the card
BZ_FOOTW    equ BZ_BAL_RB * 4   ; the ball's footprint, px (SPEC.md 128.4)
BZ_WBLK     equ 17              ; a wheel slot: the lane state bz_lbr .. bz_lL,
BZ_WSLOT    equ 2 * BZ_WBLK + 4 ; ...then its AHEAD bound and BEHIND time
BZ_WCSTO    equ 28              ; a slot's cost' (bz_wcst's place in the block)
BZ_WRB      equ 160             ; PIT counts: the lane writer's set-up of a
                                ; second rectangle (the entering rows'), which
                                ; the calibration's commits never run (PREDICTED,
                                ; about 0.5k clk raw)
BZ_WMW      equ 6               ; ...and a map word bz_lmap copies (17 clk raw
                                ; x 1.3), charged for the lane's w x h whatever
                                ; its shown lines (PREDICTED)
BZ_WPRP     equ 1900            ; PIT counts: one candidate's preparation
                                ; (bz_wprep, bz_lrect, bz_wboxm, the slot and its
                                ; two bounds; MEASURED about 7.2k clk on MartyPC's
                                ; CGA, MILL's benchmark, the final pass)
BZ_WLBUD    equ 3               ; the LEAD's budget: it ends by BZ_WLBUD / 8 of
                                ; a refresh after the wait's sample (PROVISIONAL)
%if BZ_PROPREC != 32
 %error "bz_lrecsi scales a record's index by 32 = BZ_PROPREC"
%endif
%if BZ_PROPMAX != 16
 %error "bz_ldrw, bz_lage and bz_ltru hold BZ_PROPMAX lanes"
%endif

%macro BZ_WHEEL_VARS 0
VAR bz_hold,1
VAR bz_hvoff,1
VAR bz_heavy,1
VAR bz_kpar,1                   ; GLIDE's x parity before the pan (bz_hvcam)
VAR bz_hedr,1
VAR bz_hedc,1
VAR bz_ctype,1
VAR bz_cln,1
VAR bz_wcal,1
VAR bz_wvok,1                   ; 1: the last bz_vr saw a rise, no time-out
VAR bz_wcn,1
VAR bz_wld,1
VAR bz_lr0,1
VAR bz_lr1,1
VAR bz_nlane,1                  ; the records with a lane (the first ones)
VAR bz_pidx,1                   ; the platform's record, FFh none
VAR bz_lmode,1                  ; bz_lclip: 1 the entering rows' cells too
VAR bz_ccnt,1                   ; bz_props: contact candidates this frame,
VAR bz_cbest,1                  ; the one due longest and its age,
VAR bz_cbage,1
VAR bz_must,1                   ; a must-draw ROTOR (lane + 1, 0 none), its
VAR bz_mrank,1                  ; IN cell's rank (bz_lmust), a must-draw POST
VAR bz_mustp,1                  ; (lane + 1), and the must-draw lanes seen
VAR bz_mcnt,1                   ; (those not chosen wait: bz_ndef)
VAR bz_pflag,1                  ; bit 0 the slab's box, bit 1 the slab near an edge,
                                ; bit 2 the slab's box is bz_crect2 (beside a post)
VAR bz_pov,1                    ; the slab this frame: 1 OVER the ball, 0 under,
                                ; FFh not on the card (bz_povr)
VAR bz_cold,1                   ; the contact lane's drawn pose before its sync,
VAR bz_cage,1                   ; ...and its age (bz_csync zeroes it: drawn)
VAR bz_pany,1                   ; bz_pstrip: a strip met the slab
VAR bz_wbest,1                  ; bz_props: the wheel candidate due longest,
VAR bz_wbage,1                  ; ...its age (0: none)
VAR bz_pyld,1                   ; the slab's box YIELDED its slot this frame,
VAR bz_pylp,1                   ; ...and last frame (never two running)
VAR bz_wcl,6
VAR bz_ldrw,BZ_PROPMAX
VAR bz_lage,BZ_PROPMAX
VAR bz_ltru,BZ_PROPMAX
VAR bz_lhold,BZ_PROPMAX         ; a kicked post's lit frames left on the glass
VAR bz_lkick,2 * BZ_PROPMAX     ; ...and the kick (bz_pkick) it last saw
VAR bz_wb0,2                    ; BZ_WKN words a card (bz_vinit, bz_wkc/bz_wkh):
VAR bz_wla,2                    ; the blank before window line 0, lines; a line,
VAR bz_wlb,2                    ; counts, AHEAD's (short) and BEHIND's (long);
VAR bz_wrefp,2                  ; the refresh, counts, rounded down; and the
VAR bz_wlw,2                    ; calibration's three, PREDICTED until
VAR bz_wll,2                    ; bz_wcalib replaces them
VAR bz_warr,2
VAR bz_trim,2
VAR bz_wlo,2                    ; the reckoning: the rise between lo and hi
VAR bz_whi,2                    ; after S, and the deadline
VAR bz_wdl,2
VAR bz_poff,2                   ; PROPOFF
VAR bz_pline,2
VAR bz_ptru,2
VAR bz_pox,2                    ; the slab's left px, its line at offset 0 and
VAR bz_poy,2                    ; the foot of its rise (bz_pread): the line
VAR bz_pyb,2                    ; at its low top, its sprite's last line + 1
VAR bz_pyt,2                    ; there, and its line at its high top
VAR bz_pwy,2                    ; the window the slab is tested against: its
VAR bz_pwc,2                    ; top line and first word column
VAR bz_pspr,2                   ; the slab's sprite (its record's +22), its top
VAR bz_php,2                    ; hP (whole px) and its home cell's s, Awx + Awy
VAR bz_psa,2
VAR bz_prc,8                    ; bz_pstrip: the strips' meets with the slab
VAR bz_pra,2                    ; the walk's range: block rows [ra, rb)
VAR bz_prb,2
VAR bz_crect,8
VAR bz_crect2,8                 ; the lift's box beside a lighting post (bz_pflag bit 2)
VAR bz_cgr,2                    ; bz_mkboxes: the contact's rect in bz_gr (0 none)
VAR bz_cgr2,2                   ; ...and the lift's beside it
VAR bz_lbr,2                    ; THE LANE being worked on: its first block row,
VAR bz_lcl,2                    ; first word column, words, block rows, the
VAR bz_lw,2                     ; commit's source and its row stride,
VAR bz_lh,2
VAR bz_lsrc,2
VAR bz_lsst,2
VAR bz_lra,8                    ; bz_lclip: the shown window's cells (card rows
VAR bz_lrb,8                    ; r0 r1, words x0 x1) and the entering rows',
VAR bz_wcst,2                   ; its cost' (bz_wprep), and the first and last
VAR bz_lF,2                     ; shown window lines - BZ_WBLK words a slot
VAR bz_lL,2
VAR bz_lpm,2                    ; ...its pose maps, a pose's bytes and its
VAR bz_lsz,2                    ; card rows [lq0, lq1)
VAR bz_lq0,2
VAR bz_lq1,2
VAR bz_wct,6 * BZ_WSLOT         ; bz_wheel's candidates, prepared once: each
                                ; slot BZ_WBLK words of the lane's state from
                                ; bz_lbr (bz_wsave), its AHEAD bound, its
                                ; BEHIND time (128.12.5.3)
VAR bz_wmin,2                   ; ...the cheapest cost' among them
VAR bz_wnp,1                    ; ...and how many were prepared (the clock's room)
VAR bz_lrw,2 * BZ_PROPMAX       ; each lane's first block row, its block rows
VAR bz_lhh,BZ_PROPMAX           ; and its record's kind (bz_pread: the walk
VAR bz_lknd,BZ_PROPMAX          ; reads no record for its range or a post)
VAR bz_lrc,8                    ; the lane's rect, words x lines inclusive
VAR bz_kr,8                     ; the calibration corner, px (x0 y0 x1 y1)
VAR bz_kt,8                     ; ...what it must not meet
VAR bz_cals,4
VAR bz_cT,6
%if bz_lL != bz_lbr + 2 * (BZ_WBLK - 1) || bz_wcst != bz_lbr + BZ_WCSTO || bz_lra != bz_lbr + 12
 %error "bz_wsave/bz_wload copy BZ_WBLK words from bz_lbr: bz_lbr .. bz_lL moved"
%endif
%if bz_wla != bz_wb0 + 2 || bz_wlb != bz_wb0 + 4 || bz_wrefp != bz_wb0 + 6 || bz_wlw != bz_wb0 + 8 || bz_wll != bz_wb0 + 10 || bz_warr != bz_wb0 + 12
 %error "bz_vinit copies BZ_WKN words to bz_wb0: their order moved"
%endif
%endmacro

; bz_vinit's per card: the beam (SPEC.md 128.12.5.3: window line F is reached
; 38 + F lines after a CGA rise, 98 + F after a Hercules one; a line 76 counts
; on the CGA, on the Hercules 63 where shorter is safe and 64 where longer
; is), the measured refresh rounded down, and the calibration's PREDICTED
; values (128.12.5.4) - the wheel's until the launch's first full write
; measures them
bz_wkc: dw 38, 76, 76, 19880, 284, 290, 375
bz_wkh: dw 98, 63, 64, 23420, 224, 290, 375

; -----------------------------------------------------------------------------
; bz_pread - a play's start (bz_play, after bz_pinit): the prop table's place,
; its lanes (the first records) and its platform, the slab's columns and
; track; every lane brought to its true pose in the map (128.12.4.1), the
; slice empty, the wheel uncalibrated with the trim at 100.  Preserves
; nothing.
; -----------------------------------------------------------------------------
bz_pread:
    push ds
    pop es
    xor ax, ax
    mov [bz_lr0], al
    mov [bz_lr1], al
    mov [bz_wcal], al
    mov [bz_wvok], al
    mov [bz_wld], al
    mov [bz_heavy], al
    mov [bz_hedr], ax
    mov word [bz_trim], 100
    mov word [bz_wtmin], 100
    mov word [bz_pra], 8000h    ; (the walk's range unknown: its first scan)
    mov byte [bz_pidx], 0ffh
    mov di, bz_ldrw             ; every lane unknown: bz_lfull syncs them all
    mov cx, BZ_PROPMAX / 2
    mov ax, 0ffffh
    rep stosw
    mov di, bz_lhold            ; no post lit, every kick seen (bz_pinit's)
    mov cx, BZ_PROPMAX / 2
    inc ax
    rep stosw
    mov si, bz_pkick
    mov di, bz_lkick
    mov cx, BZ_PROPMAX
    rep movsw
    push es
    mov es, [bz_cseg]
    mov si, [es:BZC_PROPOFF]
    mov [bz_poff], si
    mov cx, [es:BZC_NPROP]
    xor bx, bx                  ; BL = the record, BH = the lanes
    jcxz .done
    jmp short .rec
.done:
    jmp .done2
.rec:
    mov al, [es:si + BZP_KIND]  ; (each record's kind, and a lane's rows, where
    mov di, bx                  ; the walk reads them: bz_lknd, bz_lrw, bz_lhh)
    and di, 0ffh
    mov [bz_lknd + di], al
    test byte [es:si + BZP_FLAGS], BZ_PF_LANE
    jz .nl
    inc bh
    mov al, [es:si + BZP_LH]
    mov [bz_lhh + di], al
    shl di, 1
    mov ax, [es:si + BZP_LROW]
    mov [bz_lrw + di], ax
.nl:
    cmp byte [es:si + BZP_KIND], BZ_PK_PLATFORM
    jne .np
    mov [bz_pidx], bl           ; the LIFT's sprite (SPEC.md 128.12.6.4): its
    mov ax, [es:si + BZP_PSPR]  ; columns 16 (Awx - Awy - 1) + X0, its line
    mov [bz_pspr], ax           ; 8 (Awx + Awy) - (hP + I) + Y0, I = 0 .. 8 L
    mov ax, [es:si + BZP_PHP]
    mov [bz_php], ax
    mov al, [es:si + BZP_WX]
    mov dl, [es:si + BZP_WY]
    xor ah, ah
    xor dh, dh
    push ax
    add ax, dx
    mov [bz_psa], ax            ; (sP's base, bz_povr)
    pop ax
    push ax
    sub ax, dx
    dec ax
    shl ax, 1
    shl ax, 1
    shl ax, 1
    shl ax, 1
    add ax, [bz_x0]
    mov [bz_pox], ax
    pop ax
    add ax, dx
    shl ax, 1
    shl ax, 1
    shl ax, 1
    sub ax, [es:si + BZP_PHP]
    add ax, [bz_y0]
    mov [bz_poy], ax
    mov dl, [es:si + BZP_PL]    ; ...its rise's top line, - 8 L, and its
    shl dx, 1                   ; foot, + the sprite
    shl dx, 1
    shl dx, 1
    sub ax, dx
    mov [bz_pyt], ax
    add ax, dx
    add ax, BZ_PLH
    mov [bz_pyb], ax
.np:
    inc bl
    add si, BZ_PROPREC
    dec cx
    jz .done2
    jmp .rec
.done2:
    pop es
    mov [bz_nlane], bh
    ; (bz_lfull clears the wheel's and the contact's state too)

; -----------------------------------------------------------------------------
; bz_lfull - EVERY lane at its TRUE pose in the map, its age 0: the play's
; start and a full write (which draws every lane from its synced map, 128.12.4.1,
; 128.12.5.3), so nothing is due, no wheel runs and no contact box is needed.
; The slab is not in the map: after a full write it is not on the card either
; (bz_pline 8000h) until bz_pfull draws its box.  Preserves nothing.
; -----------------------------------------------------------------------------
bz_lfull:
    xor bx, bx
.l:
    cmp bl, [bz_nlane]
    jae .d
    call bz_ltrue
    cmp al, [bz_ldrw + bx]
    je .s
    call bz_lsync
.s:
    mov byte [bz_lage + bx], 0
    inc bx
    jmp short .l
.d:
    xor ax, ax
    mov [bz_wcn], al
    mov [bz_wld], al
    mov [bz_ctype], al
    mov word [bz_pline], BZ_PLNONE
    ret

; BX = a record's index -> SI = its offset in the course part.  Preserves all
; else.
bz_lrecsi:
    mov si, bx                  ; (five single shifts: cheaper than CL's
    shl si, 1                   ; count, and nothing to save - the step's
    shl si, 1                   ; prop path calls it often)
    shl si, 1
    shl si, 1
    shl si, 1
    add si, [bz_poff]
    ret

; -----------------------------------------------------------------------------
; bz_ltrue - lane BX's TRUE pose -> AL and [bz_ltru + BX].  A ROTOR (a
; windmill's): ((n_last + seed) AND (P - 1)) >> shift, n_last the starting n of
; the frame's LAST step - the n its gate was judged at (SPEC.md 128.12.15 item
; 1: bz_nstep - 1, the low word; 0FFFFh before the first step, as the model's
; (nstep - 1) AND 0FFFFh).  A POST (a bumper's): LIT while it has lit frames
; left on the glass (bz_lhold, SPEC.md 128.12.6.3 as the owner's preview
; amended it): a kick it has not seen (bz_pkick against bz_lkick) gives it its
; record's lit frames, and bz_props counts them off only on frames it was
; DRAWN lit.  Reads physics state; physics never reads this.  Preserves all
; but AX and the flags.
; -----------------------------------------------------------------------------
bz_ltrue:
    cmp byte [bz_lknd + bx], BZ_PK_WINDMILL
    jne .post
    push cx
    push si
    push es
    mov es, [bz_cseg]
    call bz_lrecsi
    mov ax, [bz_nstep]
    dec ax
    add ax, [es:si + BZP_SEED]
    and al, [es:si + BZP_MASK]
    mov cl, [es:si + BZP_SHIFT]
    shr al, cl
    pop es
    pop si
    pop cx
    jmp short .out
.post:                          ; (no record read but a new kick's)
    push bx
    shl bx, 1
    mov ax, [bz_pkick + bx]
    cmp ax, [bz_lkick + bx]
    mov [bz_lkick + bx], ax
    pop bx
    je .held
    push si
    push es
    mov es, [bz_cseg]
    call bz_lrecsi
    mov al, [es:si + BZP_BLIT]  ; a new kick: its lit frames
    mov [bz_lhold + bx], al
    pop es
    pop si
.held:
    cmp byte [bz_lhold + bx], 1
    sbb al, al
    inc ax                      ; 1 lit (frames left), 0 dark
.out:
    mov [bz_ltru + bx], al
    ret

; -----------------------------------------------------------------------------
; bz_ldesc - lane BX's descriptor from its record: bz_lbr, bz_lcl, bz_lw,
; bz_lh, its pose maps (bz_lpm, bz_lsz bytes a pose, bz_lsst = 2 w their row
; stride) and its card rows (bz_lq).  Preserves all but the flags.
; -----------------------------------------------------------------------------
bz_ldesc:
    push ax
    push cx
    push si
    push es
    mov es, [bz_cseg]
    call bz_lrecsi
    mov ax, [es:si + BZP_LROW]
    mov [bz_lbr], ax
    xor ah, ah
    mov al, [es:si + BZP_LCOL]
    mov [bz_lcl], ax
    mov al, [es:si + BZP_LH]
    mov [bz_lh], ax
    mov cl, al
    mov al, [es:si + BZP_LW]
    mov [bz_lw], ax
    shl ax, 1
    mov [bz_lsst], ax
    mul cl                      ; 2 w h, a pose's bytes
    mov [bz_lsz], ax
    mov ax, [es:si + BZP_LMAPS]
    mov [bz_lpm], ax
    pop es
    pop si
    pop cx
    pop ax
; bz_lq - the lane's card rows [lq0, lq1) from bz_lbr and bz_lh: (8 brow) >>
; lsh to (8 (brow + h)) >> lsh.  Preserves all but the flags.
bz_lq:
    push ax
    push cx
    mov ax, [bz_lbr]
    mov cl, 3
    shl ax, cl
    mov cl, [bz_lsh]
    shr ax, cl
    mov [bz_lq0], ax
    mov ax, [bz_lh]
    mov cl, 3
    shl ax, cl
    mov cl, [bz_lsh]
    shr ax, cl
    add ax, [bz_lq0]
    mov [bz_lq1], ax
    pop cx
    pop ax
    ret

; AL = a pose -> bz_lsrc, its map words in the course part.  Preserves all
; but the flags.
bz_lsrcp:
    push ax
    push dx
    xor ah, ah
    mul word [bz_lsz]
    add ax, [bz_lpm]
    mov [bz_lsrc], ax
    pop dx
    pop ax
    ret

; bz_lsync - lane BX's map words to pose AL, in RAM (no card write), and
; bz_ldrw = AL.  Preserves all but the flags.
bz_lsync:
    mov [bz_ldrw + bx], al
    call bz_ldesc
    call bz_lsrcp
; -----------------------------------------------------------------------------
; bz_lmap - THE MAP WRITE: bz_lh block rows of bz_lw words from the course
; part's bz_lsrc (row stride bz_lsst) into the map's rectangle at (bz_lbr,
; bz_lcl), row stride ROWB.  Through DS = ES = the course part's own segment
; (its selector on kern_mega, as the fetch and the Hercules translation
; write it, SPEC.md 128.12.12): offsets under the part's length, nothing
; through CS.  Preserves all but the flags.
; -----------------------------------------------------------------------------
bz_lmap:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    push ds
    push es
    mov di, [bz_lbr]
    mov cl, [bz_mapsh]
    add cl, 3
    shl di, cl                  ; brow x ROWB
    add di, [bz_lcl]
    add di, [bz_lcl]
    add di, BZC_MAP
    mov si, [bz_lsrc]
    mov ax, [bz_lw]
    mov bx, [bz_lsst]
    sub bx, ax
    sub bx, ax                  ; the source's step past a row's words
    mov dx, [bz_rowb]
    sub dx, ax
    sub dx, ax                  ; ...and the map's
    mov bp, [bz_lh]
    mov es, [bz_cseg]
    push es
    pop ds
.r:
    mov cx, ax
    rep movsw
    add si, bx
    add di, dx
    dec bp
    jnz .r
    pop es
    pop ds
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; AX = a0, DX = a1, BX = b0, CX = b1 -> AX = max(a0, b0), DX = min(a1, b1):
; [a0, a1) cut to [b0, b1) (empty when AX >= DX).  Preserves all else.
bz_span:
    cmp ax, bx
    jge .a
    mov ax, bx
.a:
    cmp dx, cx
    jle .b
    mov dx, cx
.b:
    ret

; -----------------------------------------------------------------------------
; bz_lclip - WHERE A COMMIT WRITES (SPEC.md 128.12.4.4 rule 1a): the lane's
; cells inside the SHOWN window (bz_R0, bz_c0: the old start address before the
; flip, the new one after it - the LEAD's) -> bz_lra, card rows and words, and
; their first and last window lines bz_lF, bz_lL; and with bz_lmode 1 (the
; wheel's) the cells rule 1 writes - this frame's entering rows (bz_dr from
; the new window's edge) less the entering column (bz_dc's) - in the slack and
; not on the glass -> bz_lrb.  No other cell: one in the entering COLUMN
; aliases a shown cell (128.2 rule 3), and any other outside the window may.
; Preserves all but the flags.
; -----------------------------------------------------------------------------
bz_lclip:
    push ax
    push bx
    push cx
    push dx
    mov ax, [bz_lq0]
    mov dx, [bz_lq1]
    mov bx, [bz_R0]
    mov cx, bx
    add cx, [bz_H]
    call bz_span
    mov [bz_lra], ax
    mov [bz_lra + 2], dx
    sub ax, bx
    sub dx, bx
    mov cl, [bz_lsh]
    shl ax, cl
    shl dx, cl
    dec dx
    mov [bz_lF], ax
    mov [bz_lL], dx
    mov ax, [bz_lcl]
    mov dx, ax
    add dx, [bz_lw]
    mov bx, [bz_c0]
    mov cx, bx
    add cx, [bz_W]
    call bz_span
    mov [bz_lra + 4], ax
    mov [bz_lra + 6], dx
    xor ax, ax
    mov [bz_lrb], ax            ; (none: r0 = r1)
    mov [bz_lrb + 2], ax
    cmp byte [bz_lmode], 0
    je .out
    mov cx, [bz_dr]
    jcxz .out
    mov bx, [bz_R0n]            ; the entering rows: moving down, the new
    or cx, cx                   ; window's bottom dr; up, its top -dr
    js .up
    add bx, [bz_H]
    sub bx, cx
    add cx, bx
    jmp short .rows
.up:
    neg cx
    add cx, bx
.rows:
    mov ax, [bz_lq0]
    mov dx, [bz_lq1]
    call bz_span
    mov [bz_lrb], ax
    mov [bz_lrb + 2], dx
    mov bx, [bz_c0n]            ; ...and their words: the new window's but the
    mov cx, bx                  ; entering column's (bz_rows's own)
    add cx, [bz_W]
    mov ax, [bz_dc]
    or ax, ax
    jz .cols
    js .left
    dec cx
    jmp short .cols
.left:
    inc bx
.cols:
    mov ax, [bz_lcl]
    mov dx, ax
    add dx, [bz_lw]
    call bz_span
    mov [bz_lrb + 4], ax
    mov [bz_lrb + 6], dx
.out:
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; bz_lwrite - THE LANE WRITER: bz_lclip's cells to the card from the map -
; the shown window's, then the entering rows' - a card row at a time, each
; row's words in turn, every line of the row (2 on the CGA, 4 on the
; Hercules: a word's lines go to the banks at one offset).  The rect's map
; entries are read once a card row and its line in the block steps by 2 rl
; bytes a row (8 lines a block, so a block row is 4 CGA card rows, 2
; Hercules ones).  A row is contiguous in every bank but where it crosses the
; 8KB ring's end, the same word in every bank: such a row takes the masked
; path, a word at a time.  The loop's state lives on the stack (SS: DS is the
; course part and ES the card inside it).  DS = ours.  Preserves all but the
; flags.
bz_lwrite:
    push si
    mov si, bz_lra
    call .rect
    mov si, bz_lrb
    call .rect
    pop si
    ret
.rect:
    push ax
    mov ax, [si + 2]
    sub ax, [si]                ; the card rows
    jle .x0
    push bx
    push cx
    push dx
    push di
    push bp
    push ds
    push es
    mov cx, [si + 6]
    sub cx, [si + 4]            ; the words
    jle .x
    push word [bz_rowb]         ; [bp + 10] ROWB
    mov dx, [bz_rl]
    shl dx, 1
    push dx                     ; [bp + 8]  2 rl: the line word's step a row
    mov dx, cx
    shl dx, 1
    push dx                     ; [bp + 6]  2 w
    neg dx
    add dx, [bz_rb]
    push dx                     ; [bp + 4]  rb - 2 w: a row's end to the next
    push ax                     ; [bp + 2]  the rows left
    push cx                     ; [bp + 0]  the words
    mov bp, sp
    mov ax, [si]                ; the first card row R
    mov bx, ax
    call bz_rbR
    mov di, [si + 4]
    shl di, 1
    add di, ax
    and di, 1fffh               ; DI = (rb R + 2 x0) mod 8192, the row's base
    mov ax, bx
    mov cl, [bz_lsh]
    shl ax, cl                  ; L0
    mov dx, ax
    and dx, 7
    shl dx, 1                   ; DX = the line's word in a block
    and ax, 0fff8h
    mov cl, [bz_mapsh]
    shl ax, cl
    add ax, BZC_MAP
    mov bx, [si + 4]
    shl bx, 1
    add bx, ax                  ; BX = the map entry of (L0, x0)
    mov al, [bz_herc]
    mov es, [bz_vseg]
    mov ds, [bz_cseg]
    or al, al
    jnz .hrow
.crow:                          ; THE CGA: two lines a card row
    mov cx, [bp + 0]
    mov ax, di
    add ax, [bp + 6]
    cmp ax, 2000h
    ja .cwrap
.cw:
    mov si, [bx]
    add si, dx
    lodsw
    stosw
    lodsw
    mov [es:di + 1ffeh], ax
    inc bx
    inc bx
    loop .cw
    jmp short .cn
.cwrap:                         ; (the row crosses the ring's end)
    mov si, [bx]
    add si, dx
    lodsw
    mov [es:di], ax
    lodsw
    mov [es:di + 2000h], ax
    inc bx
    inc bx
    inc di
    inc di
    and di, 1fffh
    loop .cwrap
.cn:
    call .next
    jnz .crow
    jmp short .done
.hrow:                          ; THE HERCULES: four
    mov cx, [bp + 0]
    mov ax, di
    add ax, [bp + 6]
    cmp ax, 2000h
    ja .hwrap
.hw:
    mov si, [bx]
    add si, dx
    lodsw
    stosw
    lodsw
    mov [es:di + 1ffeh], ax
    lodsw
    mov [es:di + 3ffeh], ax
    lodsw
    mov [es:di + 5ffeh], ax
    inc bx
    inc bx
    loop .hw
    jmp short .hn
.hwrap:
    mov si, [bx]
    add si, dx
    lodsw
    mov [es:di], ax
    lodsw
    mov [es:di + 2000h], ax
    lodsw
    mov [es:di + 4000h], ax
    lodsw
    mov [es:di + 6000h], ax
    inc bx
    inc bx
    inc di
    inc di
    and di, 1fffh
    loop .hwrap
.hn:
    call .next
    jnz .hrow
.done:
    add sp, 12
.x:
    pop es
    pop ds
    pop bp
    pop di
    pop dx
    pop cx
    pop bx
.x0:
    pop ax
    ret
; the next card row (DI is the row's end, (base + 2 w) mod 8192, and BX the
; map entry past its last word): its base, its map entries, its line in the
; block (a block's end: the map's next row); ZF = 1 when the rect is done
.next:
    add di, [bp + 4]
    and di, 1fffh
    sub bx, [bp + 6]
    add dx, [bp + 8]
    cmp dx, 16
    jb .same
    xor dx, dx
    add bx, [bp + 10]
.same:
    dec word [bp + 2]
    ret

; -----------------------------------------------------------------------------
; bz_lcost - the commit's cost' in PIT counts (SPEC.md 128.12.5.3, 128.12.5.4):
;   cost  = warr + (sum over bz_lra and bz_lrb of lines (wll + words wlw)) >> 4
;   cost' = cost x 100 / trim
; -> AX (FFFFh when it does not fit a word: never takes the wheel).  Preserves
; all else.
; -----------------------------------------------------------------------------
bz_lcost:
    push bx
    push cx
    push dx
    push si
    push di
    xor si, si
    xor di, di                  ; SI:DI = the sum, 1/16 counts
    mov bx, bz_lra
    call .rect
    mov bx, bz_lrb
    call .rect
    mov al, [bz_lw]             ; the map copy's words, w x h whatever the
    mul byte [bz_lh]            ; shown lines (BZ_WMW)
    mov dx, BZ_WMW * 16
    mul dx
    add di, ax
    adc si, dx
    mov ax, [bz_lrb + 2]        ; a second rectangle (the entering rows'):
    cmp ax, [bz_lrb]            ; its set-up, which no calibration commit
    jle .nb                     ; runs (BZ_WRB)
    mov ax, [bz_lrb + 6]
    cmp ax, [bz_lrb + 4]
    jle .nb
    add di, BZ_WRB * 16
    adc si, 0
.nb:
    mov ax, di
    mov dx, si
    mov cx, 4
.sh:
    shr dx, 1
    rcr ax, 1
    loop .sh
    add ax, [bz_warr]
    adc dx, 0
    jnz .big
    mov cx, 100
    mul cx
    mov cx, [bz_trim]
    cmp dx, cx
    jae .big
    div cx
    jmp short .out
.big:
    mov ax, 0ffffh
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    ret
.rect:
    mov ax, [bx + 2]
    sub ax, [bx]
    jle .rn
    mov cl, [bz_lsh]
    shl ax, cl
    mov cx, ax                  ; CX = the lines
    mov ax, [bx + 6]
    sub ax, [bx + 4]
    jle .rn
    mul word [bz_wlw]
    add ax, [bz_wll]
    adc dx, 0
    jz .ok
    mov ax, 0ffffh
.ok:
    mul cx
    add di, ax
    adc si, dx
.rn:
    ret

; -----------------------------------------------------------------------------
; the clock, the wheel's way (SPEC.md 128.12.5.3).  bz_elap: BX = a sample's
; bz_subs, CX = its count -> DX:AX = the PIT counts from it to the last sample.
; Preserves all else.  bz_wnow: AX = the counts from the last wait's sample S
; (bz_vsubs, bz_vpit) to the last sample, CF = 1 when that is past a word (no
; reckoning reaches that far).  Clobbers DX.
; -----------------------------------------------------------------------------
bz_elap:
    mov ax, [bz_subs]
    sub ax, bx
    xor dx, dx                  ; (0 or 1 sub-tick, nearly always: no MUL,
    or ax, ax                   ; as bz_mark)
    jz .ph
    cmp ax, 1
    jne .mul
    mov ax, BZ_SUB
    jmp short .ph
.mul:
    mov dx, BZ_SUB
    mul dx
.ph:
    add ax, cx
    adc dx, 0
    sub ax, [bz_pitl]
    sbb dx, 0
    ret

bz_wnow:
    push bx
    push cx
    mov bx, [bz_vsubs]
    mov cx, [bz_vpit]
    call bz_elap
    pop cx
    pop bx
    or dx, dx
    jz .ok
    stc
    ret
.ok:
    clc
    ret

; bz_wreck - the rise between lo and hi after S, and the deadline: bz_vedge 1
; (the wait saw it) lo = -BZ_VLAT, hi = 0; 0 (already high) lo = -16 lines,
; hi = +BZ_VLAT; deadline = lo + REFP - BZ_WMARG.  Preserves all but the flags.
bz_wreck:
    push ax
    push cx
    cmp byte [bz_vedge], 0
    je .high
    mov word [bz_wlo], -BZ_VLAT
    mov word [bz_whi], 0
    jmp short .dl
.high:
    mov ax, [bz_wlb]
    mov cl, 4
    shl ax, cl
    neg ax
    mov [bz_wlo], ax
    mov word [bz_whi], BZ_VLAT
.dl:
    mov ax, [bz_wlo]
    add ax, [bz_wrefp]
    sub ax, BZ_WMARG
    mov [bz_wdl], ax
    pop cx
    pop ax
    ret

; AX = AHEAD's bound for bz_lF: lo + (B0 + F - BZ_WGRD) x the short line, the
; latest the beam reaches the lane's first shown line.  bz_wbehind: AX = its
; pass time, hi + (B0 + L + 1 + BZ_WGRD) x the long line.  Preserve all else.
bz_wahead:
    push dx
    mov ax, [bz_lF]
    add ax, [bz_wb0]
    sub ax, BZ_WGRD
    mul word [bz_wla]
    add ax, [bz_wlo]
    pop dx
    ret

bz_wbehind:
    push dx
    mov ax, [bz_lL]
    add ax, [bz_wb0]
    add ax, 1 + BZ_WGRD
    mul word [bz_wlb]
    add ax, [bz_whi]
    pop dx
    ret

; bz_wprep - lane AL ready to commit at its true pose: its descriptor, its
; pose's source, bz_lclip's cells (by bz_lmode), and its cost' in bz_wcst.
; Preserves all but the flags.
bz_wprep:
    push ax
    push bx
    mov bl, al
    xor bh, bh
    call bz_ldesc
    mov al, [bz_ltru + bx]
    call bz_lsrcp
    call bz_lclip
    call bz_lcost
    mov [bz_wcst], ax
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; bz_wcommit - THE COMMIT of lane AL, bz_wprep'd: interrupts SHUT for the map's
; words, the lane writer and a closing clock sample (TITHE's span: one commit,
; no tick ISR - a FASTTICK sub-tick held pending by it is late by about a
; tenth of a sub-tick and never lost, 128.12.5.3); then bz_ldrw = the true
; pose (a change, always: the lane was due), its age 0, bz_wcom, and THE TRIM
; against the deadline bz_wdl: past it, trim = max(30, trim - 12) and
; bz_wover; else trim = min(100, trim + 1).  Preserves all but the flags.
; -----------------------------------------------------------------------------
bz_wcommit:
    push ax
    push bx
    push dx
    mov bl, al
    xor bh, bh
    call bz_wcore
    mov al, [bz_ltru + bx]
    mov [bz_ldrw + bx], al
    mov byte [bz_lage + bx], 0
    inc word [bz_wcom]
    call bz_wnow
    jc .over
    cmp ax, [bz_wdl]
    ja .over
    cmp word [bz_trim], 100
    jae .out
    inc word [bz_trim]
    jmp short .out
.over:
    inc word [bz_wover]
    mov ax, [bz_trim]
    sub ax, BZ_TRIMDN
    cmp ax, BZ_TRIMMIN
    jge .t
    mov ax, BZ_TRIMMIN
.t:
    mov [bz_trim], ax
    cmp ax, [bz_wtmin]
    jae .out
    mov [bz_wtmin], ax
.out:
    pop dx
    pop bx
    pop ax
    ret

; bz_wcore - a commit's timed span: interrupts shut, the map's words, the lane
; writer, the closing clock sample.  Preserves all but the flags.
bz_wcore:
    pushf
    cli
    call bz_lmap
    call bz_lwrite
    call bz_clk_sample
    popf
    ret

; -----------------------------------------------------------------------------
; bz_wheel - THE WHEEL (SPEC.md 128.12.5.3), at bz_tw after the rows: the
; candidates bz_props listed (due, shown), in raster order, committed in the
; time before the NEXT sync, reckoned from the last wait's sample.  Skipped
; (bz_wskip, the candidates staying due: late, never slowed) when the last
; wait timed out or followed a full write, or the frame is already past its
; first sync's deadline - it presents at a later sync anyway, across a refresh
; known only to a few counts.  Each candidate is PREPARED ONCE, before any
; test - while the clock leaves room to prepare it and commit it (bz_wroom;
; none prepared is a skip), and after the first while it leaves room to
; commit the cheapest prepared one too: its lane state, cost', AHEAD bound and BEHIND time into a slot
; (bz_wct), and one whose rect meets one of the frame's boxes is DROPPED -
; the box composed its drawn pose from the map before the wheel and is
; written after the flip, so it stays due (128.12.4.2).  Every test is then a
; clock sample and the arithmetic, and it and its commit are ONE critical
; section (no tick between the decision and the commit's start); and every
; test first STOPS the wheel when not even the cheapest candidate (bz_wmin)
; would end by the deadline.  Pass 1, AHEAD: each candidate whose commit ends
; before the latest beam reaches its first shown line and before the
; deadline.  Pass 2, BEHIND: each left as the earliest beam passes its last
; line, SPINNING on the clock until then (idle: the wait's time, interrupts
; open between the turns) when the commit still ends by the deadline, judged
; again at the sample it starts on; one that does not fit after the beam but
; would now is the beam's, marked for the LEAD (the first such); one that
; does not fit at all STOPS the walk - the credit is the contract.
; Preserves nothing.
; -----------------------------------------------------------------------------
bz_wheel:
    mov byte [bz_wld], 0
    cmp byte [bz_wcn], 0
    je .out
    cmp byte [bz_wvok], 0
    je .skip
    push ds
    pop es
    call bz_wreck
    mov byte [bz_lmode], 1      ; the shown cells and the entering rows'
    mov word [bz_wmin], 0ffffh
    xor bx, bx
.pr:                            ; EACH CANDIDATE PREPARED ONCE, while the
    cmp bl, [bz_wcn]            ; clock leaves room to prepare it and commit
    jae .p1                     ; it (bz_wroom: a preparation is real time,
    call bz_wroom               ; and on a frame already past its deadline
    jc .p1                      ; it is what makes the frame miss) - and,
    cmp word [bz_wmin], 0ffffh  ; once one is prepared, while it leaves room
    je .pp                      ; to commit the cheapest prepared one after
    sub ax, [bz_warr]           ; it (a commit, not another preparation)
    add ax, [bz_wmin]
    jc .p1
    cmp [bz_wdl], ax
    jb .p1
.pp:
    mov al, [bz_wcl + bx]
    call bz_wprep
    call bz_lrect
    call bz_wboxm               ; meeting a box: never the wheel's
    jnc .pk
    or byte [bz_wcl + bx], 80h
    jmp short .pn
.pk:
    call bz_wslot
    call bz_wsave
    call bz_wahead
    mov [si + 2 * BZ_WBLK], ax
    call bz_wbehind
    mov [si + 2 * BZ_WBLK + 2], ax
    mov ax, [bz_wcst]
    cmp ax, [bz_wmin]
    jae .pn
    mov [bz_wmin], ax
.pn:
    inc bx
    jmp short .pr
.p1:
    mov [bz_wnp], bl            ; the candidates the passes walk
    or bl, bl                   ; none prepared: no room, skipped
    jz .skip
    call bz_clk_sample          ; past the deadline already: skipped
    call bz_wnow
    jc .skip
    cmp ax, [bz_wdl]
    ja .skip
    xor bx, bx
.a:                             ; PASS 1: AHEAD of the beam
    cmp bl, [bz_wnp]
    jae .p2
    test byte [bz_wcl + bx], 80h
    jnz .an
    call bz_wslot
    pushf
    cli
    call bz_wtest               ; DX = now; CF = 1: nothing fits, STOP
    jc .stop
    add dx, [si + BZ_WCSTO]
    jc .anf
    cmp dx, [si + 2 * BZ_WBLK]
    ja .anf
    cmp dx, [bz_wdl]
    ja .anf
    call bz_wload
    mov al, [bz_wcl + bx]
    call bz_wcommit
    or byte [bz_wcl + bx], 80h
.anf:
    popf
.an:
    inc bx
    jmp short .a
.stop:
    popf
    ret
.p2:                            ; PASS 2: BEHIND it, as it passes each
    xor bx, bx
.b:
    cmp bl, [bz_wnp]
    jae .out
    test byte [bz_wcl + bx], 80h
    jnz .bn
    call bz_wslot
.bs:
    pushf
    cli
    call bz_wtest
    jc .stop
    mov ax, [si + 2 * BZ_WBLK + 2] ; AX = t, the beam past its last line
    cmp dx, ax
    jae .now
    add ax, [si + BZ_WCSTO]     ; t + cost' by the deadline: SPIN until
    jc .bnf                     ; the beam is past it
    cmp ax, [bz_wdl]
    ja .bnf
    popf
    jmp short .bs
.now:
    mov ax, dx                  ; past it: now + cost' by the deadline,
    add ax, [si + BZ_WCSTO]     ; judged at the sample the commit starts on,
    jc .stop                    ; or STOP
    cmp ax, [bz_wdl]
    ja .stop
    call bz_wload
    mov al, [bz_wcl + bx]
    call bz_wcommit
    popf
    jmp short .bn
.bnf:
    mov ax, dx                  ; now + cost' past the deadline: STOP; else
    add ax, [si + BZ_WCSTO]     ; the beam keeps it from this wait: the
    jc .stop                    ; LEAD's, the first such
    cmp ax, [bz_wdl]
    ja .stop
    popf
    cmp byte [bz_wld], 0
    jne .bn
    mov al, [bz_wcl + bx]
    inc ax
    mov [bz_wld], al
.bn:
    inc bx
    jmp short .b
.skip:
    inc word [bz_wskip]
.out:
    ret

; bz_wroom - CF = 1 when the clock leaves no room before the deadline to
; PREPARE one more candidate (BZ_WPRP) and commit it at the commit's fixed part
; (bz_warr) - the wheel stops preparing there, and with none prepared it is
; skipped.  Clobbers AX, DX.
bz_wroom:
    call bz_clk_sample
    call bz_wnow
    jc .x
    add ax, BZ_WPRP
    jc .x
    add ax, [bz_warr]
    jc .x
    cmp [bz_wdl], ax            ; (CF = 1: the deadline is before it)
    ret
.x:
    stc
    ret

; bz_wtest - a wheel test's clock, interrupts shut by the caller: DX = now
; (bz_wnow), CF = 1 when it is past a word or not even the cheapest
; candidate's commit (bz_wmin) would end by the deadline.  Clobbers AX.
bz_wtest:
    call bz_clk_sample
    call bz_wnow
    jc .x
    mov dx, ax
    add ax, [bz_wmin]
    jc .x
    cmp [bz_wdl], ax            ; (CF = 1: the deadline is before it)
    ret
.x:
    stc
    ret

; BX = a candidate's index -> SI = its slot in bz_wct.  Preserves all else.
bz_wslot:
    push ax
    mov ax, bx
    shl ax, 1
    mov si, ax                  ; 2i
    shl ax, 1
    add si, ax                  ; 6i
    shl ax, 1
    shl ax, 1
    shl ax, 1
    add si, ax                  ; x BZ_WSLOT (38)
    add si, bz_wct
    pop ax
    ret
%if BZ_WSLOT != 38
 %error "bz_wslot scales a candidate's index by 38 = BZ_WSLOT"
%endif

; bz_wsave - the lane state (BZ_WBLK words from bz_lbr) into slot SI;
; bz_wload - back from it.  ES = ours.  Preserve all but the flags.
bz_wsave:
    push cx
    push si
    push di
    mov di, si
    mov si, bz_lbr
    jmp short bz_wload.cp
bz_wload:
    push cx
    push si
    push di
    mov di, bz_lbr
.cp:
    mov cx, BZ_WBLK
    rep movsw
    pop di
    pop si
    pop cx
    ret

; CF = 1 when bz_lrc (words x lines, inclusive) meets one of this frame's
; boxes (bz_boxes: x0, y0, w, h).  Preserves all but the flags.
bz_wboxm:
    push ax
    push cx
    push si
    mov si, bz_boxes
    mov cx, [bz_nbox]
    jcxz .no
.b:
    mov ax, [si]
    cmp ax, [bz_lrc + 2]
    jg .n
    add ax, [si + 4]
    cmp ax, [bz_lrc]
    jle .n
    mov ax, [si + 2]
    cmp ax, [bz_lrc + 6]
    jg .n
    add ax, [si + 6]
    cmp ax, [bz_lrc + 4]
    jle .n
    stc
    jmp short .out
.n:
    add si, BZ_BOXD
    loop .b
.no:
    clc
.out:
    pop si
    pop cx
    pop ax
    ret

; -----------------------------------------------------------------------------
; bz_lead - RULE 5, THE LEAD (SPEC.md 128.12.5.3), after the column and the
; boxes: at most one commit - the lane the frame's wheel marked, when the frame
; is LIGHT (bz_heavy 0 and no contact group: the capture frame's rotor has
; bz_heavy 0) and its wait saw the rise without a time-out, the lane still
; due, its cells in the NEW window only (bz_R0, bz_c0 since bz_tf), ending
; before its AHEAD bound for its first line there and before its BUDGET -
; BZ_WLBUD / 8 of a refresh after this frame's wait - whichever is earlier
; (the lead's time is the next frame's: it is busy).  The preparation is
; billed with the commit: BX = the part the next mark closes, and a lead first
; closes it and bills itself to the box write's (BX = 5 x 4 out).  The test
; and the commit are one critical section; the commit's trim judges it against
; that deadline.  Preserves nothing but BX's meaning.
; -----------------------------------------------------------------------------
bz_lead:
    mov al, [bz_wld]
    or al, al
    jz .out
    cmp byte [bz_heavy], 0
    jne .out
    cmp byte [bz_ctype], 0
    jne .out
    cmp byte [bz_wvok], 0
    je .out
    dec ax
    mov cl, al                  ; CL = the lane
    push bx
    mov bl, al
    xor bh, bh
    mov ah, [bz_ltru + bx]
    cmp ah, [bz_ldrw + bx]
    pop bx
    je .out
    cmp bx, 5 * 4
    je .m
    call bz_mark
    mov bx, 5 * 4
.m:
    push ds
    pop es
    mov byte [bz_lmode], 0
    mov al, cl
    call bz_wprep
    mov dx, [bz_lra]
    cmp dx, [bz_lra + 2]
    jge .out
    mov dx, [bz_lra + 4]
    cmp dx, [bz_lra + 6]
    jge .out
    call bz_wreck
    call bz_wahead
    mov si, ax                  ; SI = AHEAD's bound
    mov ax, [bz_wrefp]
    shr ax, 1
    shr ax, 1
    shr ax, 1
    mov dx, BZ_WLBUD
    mul dx                      ; AX = the budget
    cmp ax, si
    jbe .dl
    mov ax, si
.dl:
    mov [bz_wdl], ax
    pushf
    cli
    call bz_clk_sample
    call bz_wnow
    jc .no
    add ax, [bz_wcst]
    jc .no
    cmp ax, [bz_wdl]
    ja .no
    mov al, cl
    call bz_wcommit
    popf
    inc word [bz_wlead]
    ret
.no:
    popf
.out:
    ret

; -----------------------------------------------------------------------------
; bz_wcalib - THE CALIBRATION (SPEC.md 128.12.5.4), once a launch, at the end
; of its first full write and before its sub-ticks are discarded: the COMMIT
; path itself - the map copy, the lane writer, the closing clock sample - on a
; pseudo-lane whose pose map is its own map words, over 1 block row x 4 words,
; 3 x 4 and 3 x 2, eight times each, one commit a span, interrupts shut inside
; each.  Idempotent: the words are copied onto themselves and the full write
; has just put exactly those bytes on the card from the same map.  The
; rectangle is the first of the window's four corners holding no lane, no
; track and none of the ball's footprint (bz_wcorner; the tool refuses a
; course without one).  With T1, T3, T3n the three means, in PIT counts:
;   wlw = 16 (T3 - T3n) / 48, wll = (T3 - T1) - 4 wlw (1/16 counts),
;   warr = T1 - (wll + 4 wlw) / 2, each at least 1.
; Preserves nothing.
; -----------------------------------------------------------------------------
bz_wcalib:
    cmp byte [bz_wcal], 0
    je .go
    ret
.go:
    mov byte [bz_wcal], 1
    call bz_wcorner
    jc .out
    mov byte [bz_lmode], 0
    mov ax, [bz_rowb]
    mov [bz_lsst], ax           ; the pose map is the map itself
    mov word [bz_lw], 4
    mov word [bz_lh], 1
    call bz_wspan
    mov [bz_cT], ax             ; T1
    mov word [bz_lh], 3
    call bz_wspan
    mov [bz_cT + 2], ax         ; T3
    mov word [bz_lw], 2
    call bz_wspan
    mov [bz_cT + 4], ax         ; T3n
    mov ax, [bz_cT + 2]
    sub ax, [bz_cT + 4]
    jae .w
    xor ax, ax
.w:
    mov cx, 16
    mul cx
    mov cx, 48
    div cx
    call .min1
    mov [bz_wlw], ax
    shl ax, 1
    shl ax, 1
    mov bx, ax                  ; BX = 4 wlw
    mov ax, [bz_cT + 2]
    sub ax, [bz_cT]
    sub ax, bx
    call .min1
    mov [bz_wll], ax
    add ax, bx
    shr ax, 1
    mov dx, [bz_cT]
    sub dx, ax
    xchg ax, dx
    call .min1
    mov [bz_warr], ax
.out:
    ret
.min1:
    or ax, ax
    jg .m1
    mov ax, 1
.m1:
    ret

; bz_wspan - the mean of BZ_CALN timed commits of the rectangle (bz_lbr,
; bz_lcl, bz_lw x bz_lh) onto itself -> AX, PIT counts.  Clobbers BX, CX, DX,
; SI.  (bz_wnow inside a span spends DX: BX, CX hold the opening sample.)
bz_wspan:
    mov ax, [bz_lbr]
    mov cl, [bz_mapsh]
    add cl, 3
    shl ax, cl
    add ax, [bz_lcl]
    add ax, [bz_lcl]
    add ax, BZC_MAP
    mov [bz_lsrc], ax
    call bz_lq
    call bz_lclip
    push ds
    pop es
    mov si, bz_wct              ; the pseudo-lane in a wheel slot, loaded
    call bz_wsave               ; inside each span as a wheel commit's is
    xor ax, ax
    mov [bz_cals], ax
    mov [bz_cals + 2], ax
    mov si, BZ_CALN
.s:
    pushf                       ; ONE SPAN: from a clock sample, through the
    cli                         ; reckoning the wheel makes from it (bz_wnow,
    call bz_clk_sample          ; its result unused here), to the commit's own
    mov bx, [bz_subs]           ; closing sample - what a commit costs after
    mov cx, [bz_pitl]           ; the sample its test is made on
    call bz_wnow
    push si
    mov si, bz_wct
    call bz_wload
    pop si
    call bz_wcore
    popf
    call bz_elap
    add [bz_cals], ax
    adc [bz_cals + 2], dx
    dec si
    jnz .s
    mov ax, [bz_cals]
    mov dx, [bz_cals + 2]
    mov cx, 3
.d:
    shr dx, 1
    rcr ax, 1
    loop .d
    or dx, dx
    jz .o
    mov ax, 0ffffh
.o:
    ret

; bz_wcorner - the calibration's rectangle: the window's four corners of 4
; words x 3 WHOLE block rows - top-left, top-right, bottom-left, bottom-right,
; bbcourse.check_bounds's order - the first free of lanes, the slab's track
; and the ball's footprint -> bz_lbr, bz_lcl; CF = 1 none.  Clobbers AX, BX,
; CX, DX, SI, DI.
bz_wcorner:
    mov ax, [bz_R0]
    mov cl, [bz_lsh]
    shl ax, cl                  ; the window's top line
    mov dx, ax
    add ax, 7
    mov cl, 3
    shr ax, cl
    mov si, ax                  ; SI = the first whole block row
    add dx, BZ_LINES
    shr dx, cl
    sub dx, 3
    mov di, dx                  ; DI = the last three's first
    mov bx, [bz_c0]
    mov cx, bx
    add cx, [bz_W]
    sub cx, 4
    mov ax, bx
    mov dx, si
    call bz_wctry
    jnc .ok
    mov ax, cx
    call bz_wctry
    jnc .ok
    mov ax, bx
    mov dx, di
    call bz_wctry
    jnc .ok
    mov ax, cx
    call bz_wctry
.ok:
    ret

; AX = a word column, DX = a block row: CF = 1 when the corner there meets a
; lane, the slab's track or the ball's footprint; else bz_lcl, bz_lbr = it.
; Preserves BX, CX, SI, DI.
bz_wctry:
    push bx
    push cx
    push si
    push di
    push ax
    push dx
    mov cl, 3
    shl ax, cl
    mov [bz_kr], ax
    add ax, 32
    mov [bz_kr + 4], ax
    shl dx, cl
    mov [bz_kr + 2], dx
    add dx, 24
    mov [bz_kr + 6], dx
    mov si, bz_kt
    mov ax, [bz_px]             ; the ball's footprint (SPEC.md 128.4)
    and al, 0fch
    mov [si], ax
    add ax, BZ_FOOTW
    mov [si + 4], ax
    mov ax, [bz_py]
    mov [si + 2], ax
    add ax, BZ_BAL_ROWS
    mov [si + 6], ax
    call bz_kmeet
    jc .out
    cmp byte [bz_pidx], 0ffh    ; the slab's rise
    je .lanes
    mov ax, [bz_pox]
    mov [si], ax
    add ax, BZ_PLW
    mov [si + 4], ax
    mov ax, [bz_pyt]
    mov [si + 2], ax
    mov ax, [bz_pyb]
    mov [si + 6], ax
    call bz_kmeet
    jc .out
.lanes:
    xor bx, bx
.l:
    cmp bl, [bz_nlane]
    jae .free
    call bz_ldesc
    mov cl, 3
    mov ax, [bz_lcl]
    shl ax, cl
    mov [si], ax
    mov ax, [bz_lcl]
    add ax, [bz_lw]
    shl ax, cl
    mov [si + 4], ax
    mov ax, [bz_lbr]
    shl ax, cl
    mov [si + 2], ax
    mov ax, [bz_lbr]
    add ax, [bz_lh]
    shl ax, cl
    mov [si + 6], ax
    call bz_kmeet
    jc .out
    inc bx
    jmp short .l
.free:
    pop dx
    pop ax
    mov [bz_lcl], ax
    mov [bz_lbr], dx
    clc
    jmp short .ret
.out:
    pop dx
    pop ax
.ret:
    pop di
    pop si
    pop cx
    pop bx
    ret

; SI = a px rect (x0 y0 x1 y1, ends exclusive): CF = 1 when it meets bz_kr.
; Preserves all but the flags.
bz_kmeet:
    push ax
    mov ax, [si]
    cmp ax, [bz_kr + 4]
    jge .no
    mov ax, [bz_kr]
    cmp ax, [si + 4]
    jge .no
    mov ax, [si + 2]
    cmp ax, [bz_kr + 6]
    jge .no
    mov ax, [bz_kr + 2]
    cmp ax, [si + 6]
    jge .no
    pop ax
    stc
    ret
.no:
    pop ax
    clc
    ret

; -----------------------------------------------------------------------------
; bz_props - THE WALK (SPEC.md 128.12.5.2), once a frame in bz_t0 after the
; steps and bz_foot, before the camera; nothing is written to the card.  The
; lanes kept are a SLICE [bz_lr0, bz_lr1) of those meeting the RANGE - the
; shown window's block rows widened by two on each side, the whole width
; (lanes are sorted by first block row, so the slice is contiguous and moves
; by a compare or two, and is not looked at when the range has not moved); a
; lane outside it costs nothing, and the walk reads no record for a lane's
; range or a post (bz_lrw, bz_lhh, bz_lknd; a descriptor only for a lit post
; or a due lane).  For each lane in it:
;   0. a POST's lit frames: one counted off when it begins the frame drawn
;      lit, all of them when it is wholly out of the shown window;
;   1. its TRUE pose (bz_ltrue);
;   2. wholly outside the shown window and true != drawn: its map words now,
;      in RAM (bz_lsync) - which also syncs a lane entering the slice, two
;      block rows before any strip can reach it;
;   3. due and shown: its age + 1, bz_wlate at BZ_WLAG frames;
;   4. MUST-DRAW: a windmill whose IN cell is on bz_wol (the ball's 3 x 3) and
;      whose true gate state differs from its drawn one (bz_must: of two, the
;      IN cell nearer the ball's centre, then the first), or a post LIGHTING
;      (bz_mustp, the first); else meeting the ball's or the shadow's old or
;      new footprint, a CONTACT candidate; else a WHEEL candidate (bz_wcl,
;      raster order; bz_wheel drops one meeting a box).
; THE PLATFORM (128.12.15 item 3): its whole rise outside the walk's range,
; not on the card (bz_pline 8000h) and not computed; else its true line from
; n; its drawn and its true footprint both outside the shown window, its drawn
; line follows in RAM; else, its line changed, its box.
; THE CONTACT GROUP, at most one: a must-draw rotor, else the slab's box (a
; post lighting waits a frame for it: the box cannot, SPEC.md 128.12.4.3),
; else a post lighting, else the contact candidate due longest (the highest
; bz_lage, then the lowest index) - on a frame whose ball and shadow are ONE
; box between them, with no occluder pass and the ball outside the edge zone,
; or on any frame once it has been due BZ_WPRF frames - else the WHEEL
; candidate due longest once it has been due BZ_WPRO frames on such a frame,
; or BZ_WPRF on any (bz_wpro: PROMOTED; the slab's box yields it one frame).  Every other contact
; candidate and must-draw lane WAITS, its map unsynced (bz_ndef): display
; only.  bz_heavy (128.12.7) from those choices and the ball before the
; camera.  Preserves nothing.
; -----------------------------------------------------------------------------
bz_props:
    mov al, [bz_pyld]
    mov [bz_pylp], al
    xor ax, ax
    mov [bz_pyld], al
    mov [bz_wbage], al
    mov [bz_ctype], al
    mov [bz_wcn], al
    mov [bz_heavy], al
    mov [bz_ccnt], al
    mov [bz_must], al
    mov [bz_mustp], al
    mov [bz_mcnt], al
    mov [bz_pflag], al
    mov [bz_hedr], ax
    cmp byte [bz_first], 0      ; the first frame is a centred full write:
    je .go                      ; bz_lfull's
    ret
.go:
    cmp byte [bz_nlane], 0      ; no lane and no lift (BENCH, FIRST, TRIAL):
    jne .go2                    ; nothing to walk, only the level (MEASURED,
    cmp byte [bz_pidx], 0ffh    ; the final pass: the walk's ranges and the
    jne .go2                    ; choice cost 1.1k clk a BENCH frame)
    jmp .level
.go2:
    mov ax, [bz_R0]
    mov cl, [bz_lsh]
    shl ax, cl
    mov [bz_pwy], ax            ; the shown window's top line
    mov dx, [bz_c0]             ; ...and first column (the slab's tests)
    mov [bz_pwc], dx
    mov cl, 3                   ; THE RANGE: block rows [ra, rb)
    mov dx, ax
    shr dx, cl
    sub dx, 2
    add ax, BZ_LINES - 1
    shr ax, cl
    add ax, 3
    cmp dx, [bz_pra]            ; the last frame's: the slice stands
    jne .rng
    cmp ax, [bz_prb]
    je .walk
.rng:
    mov [bz_pra], dx
    mov [bz_prb], ax
    xor bx, bx                  ; lr0 on while that lane cannot reach ra (its
    mov bl, [bz_lr0]            ; brow + 3 <= ra: h is at most 3), back while
.f0:                            ; the one before it can
    cmp bl, [bz_nlane]
    jae .b0
    mov si, bx
    shl si, 1
    mov cx, [bz_lrw + si]
    add cx, 3
    cmp cx, dx
    jg .b0
    inc bx
    jmp short .f0
.b0:
    or bx, bx
    jz .b0d
    dec bx
    mov si, bx
    shl si, 1
    mov cx, [bz_lrw + si]
    add cx, 3
    cmp cx, dx
    jg .b0
    inc bx
.b0d:
    mov [bz_lr0], bl
    mov bl, [bz_lr1]            ; lr1 on while that lane starts above rb, back
.f1:                            ; while the one before it does not
    cmp bl, [bz_nlane]
    jae .b1
    mov si, bx
    shl si, 1
    cmp [bz_lrw + si], ax
    jge .b1
    inc bx
    jmp short .f1
.b1:
    or bx, bx
    jz .b1d
    dec bx
    mov si, bx
    shl si, 1
    cmp [bz_lrw + si], ax
    jge .b1
    inc bx
.b1d:
    mov [bz_lr1], bl
.walk:
    xor bx, bx
    mov bl, [bz_lr0]
.lane:
    cmp bl, [bz_lr1]
    jb .l1
    jmp .plat
.l1:
    mov si, bx                  ; in the range exactly
    shl si, 1
    mov ax, [bz_lrw + si]
    cmp ax, [bz_prb]
    jge .nx
    mov cl, [bz_lhh + bx]
    xor ch, ch
    add ax, cx
    cmp ax, [bz_pra]
    jg .in
.nx:
    jmp .next
.in:
    cmp byte [bz_lhold + bx], 0 ; 0. a lit post's frames ON THE GLASS: one
    je .t                       ; counted off each frame that begins with it
    call bz_ldesc               ; drawn lit; none left once it is wholly
    call bz_lshown              ; out of the shown window
    jnc .h0
    cmp byte [bz_ldrw + bx], 1
    jne .t
    dec byte [bz_lhold + bx]
    jmp short .t
.h0:
    mov byte [bz_lhold + bx], 0
.t:
    call bz_ltrue               ; 1. the true pose
    cmp al, [bz_ldrw + bx]
    jne .due
    mov byte [bz_lage + bx], 0
    jmp short .nx
.due:
    call bz_ldesc
    call bz_lshown
    jc .shown
    call bz_lsync               ; 2. wholly outside: the map now, in RAM
    mov byte [bz_lage + bx], 0
    jmp short .nx
.shown:
    mov al, [bz_lage + bx]      ; 3. its age
    inc al
    jz .aged
    mov [bz_lage + bx], al
    cmp al, BZ_WLAG
    jne .aged
    inc word [bz_wlate]
.aged:
    call bz_lmust               ; 4. a must-draw rotor or post ...
    jnc .cont
    inc byte [bz_mcnt]
    cmp al, 0ffh
    je .mp
    cmp byte [bz_must], 0       ; (a rotor: of two, the IN cell nearer the
    je .mr                      ; ball's centre, then the first)
    cmp al, [bz_mrank]
    jae .next
.mr:
    mov [bz_mrank], al
    lea ax, [bx + 1]
    mov [bz_must], al
    jmp short .next
.mp:
    cmp byte [bz_mustp], 0      ; (a post: the first)
    jne .next
    lea ax, [bx + 1]
    mov [bz_mustp], al
    jmp short .next
.cont:
    call bz_lfoot               ; ...a contact candidate ...
    jnc .wheel
    inc byte [bz_ccnt]
    mov al, [bz_lage + bx]
    cmp byte [bz_ccnt], 1
    je .best
    cmp al, [bz_cbage]          ; (due longer than the best so far; the lower
    jbe .next                   ; index wins a tie: it came first)
.best:
    mov [bz_cbest], bl
    mov [bz_cbage], al
    jmp short .next
.wheel:
    mov al, [bz_wcn]            ; ...or the wheel's (at most six meet a
    cmp al, 6                   ; window, 128.12.4.6)
    jae .next
    cbw
    mov di, ax
    mov [bz_wcl + di], bl
    inc byte [bz_wcn]
    mov al, [bz_lage + bx]      ; (the one due longest: the first of a tie)
    cmp al, [bz_wbage]
    jbe .next
    mov [bz_wbage], al
    mov [bz_wbest], bl
.next:
    inc bx
    jmp .lane
.plat:
    mov bl, [bz_pidx]           ; THE PLATFORM
    cmp bl, 0ffh
    je .choose
    mov cl, 3                   ; its whole rise [pyt, pyb) outside the
    mov dx, [bz_pra]            ; range's lines [8 ra, 8 rb): not on the card,
    shl dx, cl                  ; and no strip can reach it this frame
    cmp [bz_pyb], dx
    jle .pfar
    mov dx, [bz_prb]
    shl dx, cl
    cmp [bz_pyt], dx
    jl .pin
.pfar:
    mov word [bz_pline], BZ_PLNONE
    jmp short .choose
.pin:
    xor bh, bh
    call bz_ptrue
    call bz_pshown
    jc .pshown
    mov dx, ax                  ; the TRUE footprint outside the window ...
    mov ax, [bz_pline]
    cmp ax, BZ_PLNONE
    je .pout
    call bz_pshown              ; ...and the DRAWN one: drawn = true, in RAM
    jc .pbox                    ; (the drawn one shown: its box erases it)
.pout:
    mov [bz_pline], dx
    jmp short .choose
.pshown:
    cmp ax, [bz_pline]
    je .pnear
.pbox:
    or byte [bz_pflag], 1       ; shown and its line changed: its box
    mov ax, [bz_ptru]
.pnear:
    call bz_pnear
    jnc .choose
    or byte [bz_pflag], 2
.choose:
    mov al, [bz_must]           ; THE CONTACT GROUP: a must-draw rotor, ...
    or al, al
    jnz .mlane
    test byte [bz_pflag], 1     ; ...the slab's box, ...
    jz .nopl
    mov al, [bz_pylp]           ; (which YIELDS a frame - never two running,
    or al, [bz_onp]             ; never under a ball the lift carries or
    or al, [bz_mustp]           ; beside a post lighting - to a wheel lane
    jnz .pkeep                  ; promoted (bz_wpro): its drawn line holds,
    call bz_wpro                ; and the drawn line is what every writer
    jnc .pkeep                  ; draws, so the card stays the map's)
    and byte [bz_pflag], 0feh
    mov byte [bz_pyld], 1
    jmp short .promo
.pkeep:
    cmp byte [bz_mustp], 0      ; (with a post lighting: the post is the
    je .slab                    ; group and the box a SECOND rect, which
    or byte [bz_pflag], 4       ; bz_mkboxes keeps when the frame has room -
    mov di, bz_crect2           ; else the post waits a frame: the box
    call bz_cslabr              ; cannot)
    mov al, [bz_mustp]
    jmp short .mlane
.slab:
    call bz_cslab
    jmp short .chosen
.nopl:
    mov al, [bz_mustp]          ; ...a post lighting, ...
    or al, al
    jz .nomust
.mlane:
    dec byte [bz_mcnt]
    dec ax
    mov bl, al
    xor bh, bh
    call bz_csync
    jmp short .chosen
.nomust:
    cmp byte [bz_ccnt], 0       ; ...a contact candidate, on a frame that
    je .wp                      ; allows one or once it has waited BZ_WLAG
    call bz_conok               ; frames - BZ_WPRF as built, the final pass:
    jc .cand                    ; a rotor's pose can change again in 5 (it
    cmp byte [bz_cbage], BZ_WPRF ; would otherwise wait for as long as the
    jae .cand                   ; ball rests on it), ...
.wp:
    call bz_wpro                ; ...else a WHEEL lane due BZ_WPRO frames
    jnc .level                  ; (the wait could not take it: PROMOTED)
.promo:
    mov bl, [bz_wbest]
    xor bh, bh
    call bz_wdrop
    call bz_csync
    jmp short .chosen
.cand:
    mov bl, [bz_cbest]
    xor bh, bh
    call bz_csync
    dec byte [bz_ccnt]
.chosen:
    inc word [bz_ncon]
    mov byte [bz_heavy], 2
.level:
    mov al, [bz_ccnt]           ; the contact candidates and must-draw lanes
    add al, [bz_mcnt]           ; that wait
    xor ah, ah
    add [bz_ndef], ax
    mov al, [bz_hvoff]          ; a harness's A/B, or a hidden ball: none
    or al, [bz_tube]
    jz .lv
    mov byte [bz_heavy], 0
    ret
.lv:
    cmp byte [bz_heavy], 0
    jne .edge
    call bz_hv1
    jnc .out
    mov byte [bz_heavy], 1
.edge:
    call bz_pedge               ; a heavy frame's edge clause, for the camera
.out:
    ret

; bz_wpro - CF = 1 when the wheel candidate due longest (bz_wbest) is
; PROMOTED to the contact slot (the final pass, SPEC.md 128.12.4.3): due
; BZ_WPRO frames on a frame that allows a contact lane (bz_conok), or
; BZ_WPRF on any frame - so no lane reaches bz_wlate while a box can take it,
; and a rotor skips no pose it holds for BZ_WPRF frames.  Clobbers AX, BX, SI.
bz_wpro:
    cmp byte [bz_wbage], BZ_WPRO
    jb .no
    cmp byte [bz_wbage], BZ_WPRF
    jae .yes
    jmp bz_conok
.yes:
    stc
    ret
.no:
    clc
    ret

; bz_wdrop - lane BL out of the wheel's list (bz_wcl, bz_wcn): the contact
; group draws it.  Clobbers AX, CX, SI.
bz_wdrop:
    xor cx, cx
    mov cl, [bz_wcn]
    mov si, bz_wcl
.f:
    jcxz .x
    mov al, [si]
    inc si
    dec cx
    cmp al, bl
    jne .f
.s:
    jcxz .d
    mov al, [si]
    mov [si - 1], al
    inc si
    dec cx
    jmp short .s
.d:
    dec byte [bz_wcn]
.x:
    ret

; CF = 1 when lane BX (bz_ldesc'd) meets the SHOWN window (bz_R0, bz_c0).
; Preserves all but the flags.
bz_lshown:
    push ax
    mov ax, [bz_c0]
    add ax, [bz_W]
    cmp [bz_lcl], ax
    jge .no
    mov ax, [bz_lcl]
    add ax, [bz_lw]
    cmp ax, [bz_c0]
    jle .no
    mov ax, [bz_R0]
    add ax, [bz_H]
    cmp [bz_lq0], ax
    jge .no
    mov ax, [bz_lq1]
    cmp ax, [bz_R0]
    jle .no
    pop ax
    stc
    ret
.no:
    pop ax
    clc
    ret

; CF = 1 when lane BX is MUST-DRAW (SPEC.md 128.12.5.2): a windmill whose prop
; index is on bz_wol (its IN cell in the ball's 3 x 3) and whose TRUE pose's
; gate state - closed for poses c0 >> shift .. c1 >> shift - 1 - differs from
; its DRAWN pose's, AL = its IN cell's RANK (0 the window's centre, 1 a side,
; 2 a corner: the nearer to the ball wins a frame with two); or a post
; LIGHTING, true lit and drawn dark (the owner's preview: a hit always shows,
; whatever the wheel's credit), AL = FFh.  Preserves all but AL and the flags.
bz_lmust:
    push cx
    push dx
    push si
    push di
    cmp byte [bz_lknd + bx], BZ_PK_WINDMILL
    jne .post
    mov cl, [bz_wol]            ; (a count, then (cell, index) pairs)
    xor ch, ch
    jcxz .no
    mov di, bz_wol + 1
.w:
    cmp [di + 1], bl
    je .on
    inc di
    inc di
    loop .w
    jmp short .no
.on:
    mov dl, [di]                ; DL = the IN cell
    push es
    mov es, [bz_cseg]
    call bz_lrecsi
    mov cl, [es:si + BZP_SHIFT]
    mov ah, [es:si + BZP_TC0]
    shr ah, cl                  ; AH = the first closed pose
    mov ch, [es:si + BZP_TC1]
    pop es
    shr ch, cl
    sub ch, ah                  ; CH = the closed poses
    mov al, [bz_ltru + bx]
    sub al, ah
    cmp al, ch
    sbb cl, cl                  ; CL = FFh: the true pose's gate is closed
    mov al, [bz_ldrw + bx]
    sub al, ah
    cmp al, ch
    sbb al, al
    xor al, cl
    jz .no
    mov al, 0                   ; its rank
    cmp dl, 4
    je .yes
    inc ax
    test dl, 1
    jnz .yes
    inc ax
    jmp short .yes
.post:                          ; a POST LIGHTING: true lit over drawn dark
    mov al, [bz_ltru + bx]      ; (the owner's preview: a hit always shows)
    cmp al, [bz_ldrw + bx]
    mov al, 0ffh
    ja .yes
.no:
    clc
    jmp short .out
.yes:
    stc
.out:
    pop di
    pop si
    pop dx
    pop cx
    ret

; bz_lrect - lane BX's (bz_ldesc'd) rect into bz_lrc: words x lines,
; inclusive.  Preserves all but the flags.
bz_lrect:
    push ax
    push cx
    mov cl, 3
    mov ax, [bz_lcl]
    mov [bz_lrc], ax
    add ax, [bz_lw]
    dec ax
    mov [bz_lrc + 2], ax
    mov ax, [bz_lbr]
    shl ax, cl
    mov [bz_lrc + 4], ax
    mov ax, [bz_lh]
    shl ax, cl
    add ax, [bz_lrc + 4]
    dec ax
    mov [bz_lrc + 6], ax
    pop cx
    pop ax
    ret

; CF = 1 when lane BX (bz_ldesc'd) meets the ball's or the shadow's old or new
; footprint (bz_ofx0, bz_sox0, bz_nfx0, bz_snx0: words x lines, inclusive) - a
; hidden ball (bz_tube) has no new one.  Its rect is left in bz_lrc.
; Preserves all but the flags.
bz_lfoot:
    push si
    call bz_lrect
    cmp byte [bz_oldv], 0
    je .new
    mov si, bz_ofx0
    call bz_rmeet
    jc .out
    cmp byte [bz_sov], 0
    je .new
    mov si, bz_sox0
    call bz_rmeet
    jc .out
.new:
    cmp byte [bz_tube], 0
    jne .no
    mov si, bz_nfx0
    call bz_rmeet
    jc .out
    cmp byte [bz_shc], 0
    je .no
    mov si, bz_snx0
    call bz_rmeet
    jmp short .out
.no:
    clc
.out:
    pop si
    ret

; SI = a rect, words x lines inclusive: CF = 1 when it meets bz_lrc.
; Preserves all but the flags.
bz_rmeet:
    push ax
    mov ax, [si]
    cmp ax, [bz_lrc + 2]
    jg .no
    mov ax, [bz_lrc]
    cmp ax, [si + 2]
    jg .no
    mov ax, [si + 4]
    cmp ax, [bz_lrc + 6]
    jg .no
    mov ax, [bz_lrc + 4]
    cmp ax, [si + 6]
    jg .no
    pop ax
    stc
    ret
.no:
    pop ax
    clc
    ret

; bz_csync - lane BX is the CONTACT group: its map words synced now (drawn =
; true), its rect (words x lines, inclusive) the group's.  Preserves all but
; the flags.
bz_csync:
    push ax
    push cx
    mov al, [bz_ldrw + bx]      ; (its drawn pose and its age, should a strip
    mov [bz_cold], al           ; meeting the slab take the slot back:
    mov al, [bz_lage + bx]      ; bz_pstrip, bz_pyield)
    mov [bz_cage], al
    mov byte [bz_lage + bx], 0  ; drawn this frame: a pose due NEXT frame
                                ; ages from 1, as after a wheel commit
    mov al, [bz_ltru + bx]
    call bz_lsync
    mov byte [bz_ctype], 1
    mov [bz_cln], bl
    mov cl, 3
    mov ax, [bz_lcl]
    mov [bz_crect], ax
    add ax, [bz_lw]
    dec ax
    mov [bz_crect + 2], ax
    mov ax, [bz_lbr]
    shl ax, cl
    mov [bz_crect + 4], ax
    mov ax, [bz_lh]
    shl ax, cl
    add ax, [bz_crect + 4]
    dec ax
    mov [bz_crect + 6], ax
    pop cx
    pop ax
    ret

; bz_pyield - bz_mkboxes found no room for the lift's box beside a lighting
; post (bz_pflag bit 2): the post WAITS a frame - its map words back to its
; drawn pose, bz_ndef - and the box is the contact group (bz_crect2 to
; bz_crect, bz_ctype 2).  Clobbers AX, BX.
bz_pyield:
    mov bl, [bz_cln]
    xor bh, bh
    mov al, [bz_cold]
    call bz_lsync
    mov al, [bz_cage]
    mov [bz_lage + bx], al
    inc word [bz_ndef]
    and byte [bz_pflag], 0fbh
    mov byte [bz_ctype], 2
    mov ax, [bz_crect2]
    mov [bz_crect], ax
    mov ax, [bz_crect2 + 2]
    mov [bz_crect + 2], ax
    mov ax, [bz_crect2 + 4]
    mov [bz_crect + 4], ax
    mov ax, [bz_crect2 + 6]
    mov [bz_crect + 6], ax
    ret

; bz_cslab - the PLATFORM's box is the contact group (SPEC.md 128.12.4.3): its
; drawn and true footprints, one box (the slab moves at most 6 lines in an
; 8-step frame), BZ_BOXW words from its columns; then its drawn line is the
; true one (bz_pline).  Preserves all but the flags.
bz_cslab:
    mov byte [bz_ctype], 2
    push di
    mov di, bz_crect
    call bz_cslabr
    pop di
    ret
; bz_cslabr - the same, the rect into DI (bz_crect, or bz_crect2 beside a
; lighting post: SPEC.md 128.12.5.2), bz_ctype untouched.
bz_cslabr:
    push ax
    push cx
    push dx
    inc word [bz_npbx]
    mov ax, [bz_pox]
    mov cl, 3
    shr ax, cl
    mov [di], ax
    add ax, BZ_BOXW - 1
    mov [di + 2], ax
    mov ax, [bz_ptru]
    mov dx, ax
    mov cx, [bz_pline]
    cmp cx, BZ_PLNONE
    je .one
    cmp cx, ax
    jge .lo
    mov ax, cx
.lo:
    cmp cx, dx
    jle .one
    mov dx, cx
.one:
    mov [di + 4], ax
    add dx, BZ_PLH - 1
    mov [di + 6], dx
    mov ax, [bz_ptru]
    mov [bz_pline], ax
    pop dx
    pop cx
    pop ax
    ret

; bz_ptrue - the LIFT's (record BX) TRUE line at n = bz_nstep -> AX and
; bz_ptru: its rise bbcourse.plat_pos's way (SPEC.md 128.12.6.4) - m = (n +
; seed) AND (P - 1), q = m in the first half of the period and P - 1 - m in
; the second, I = min(PMAX, max(0, q - W) v) - and the line poy - (I >> 8).
; Preserves all but AX and the flags.
bz_ptrue:
    push dx
    push si
    push es
    mov es, [bz_cseg]
    call bz_lrecsi
    mov ax, [bz_nstep]
    add ax, [es:si + BZP_SEED]
    mov dl, [es:si + BZP_MASK]
    and al, dl                  ; AL = m
    shr dl, 1                   ; DL = P / 2 - 1
    cmp al, dl
    jbe .q
    mov ah, [es:si + BZP_MASK]
    sub ah, al
    mov al, ah                  ; q = P - 1 - m
.q:
    xor ah, ah
    sub al, [es:si + BZP_PW]
    jnc .qw
    xor al, al
.qw:
    mul word [es:si + BZP_PV]
    cmp ax, [es:si + BZP_PMAX]
    jbe .pm
    mov ax, [es:si + BZP_PMAX]
.pm:
    mov al, ah
    xor ah, ah                  ; I >> 8, whole px
    neg ax
    add ax, [bz_poy]
    mov [bz_ptru], ax
    pop es
    pop si
    pop dx
    ret

; AX = the slab's line: CF = 1 when its sprite (bz_pox, BZ_PLW x BZ_PLH) meets
; the window bz_pwy, bz_pwc (bz_props: the shown one; bz_pfull: a full
; write's new one).  Preserves all but the flags.
bz_pshown:
    push dx
    mov dx, [bz_pwy]
    add dx, BZ_LINES
    cmp ax, dx
    jge .no
    mov dx, ax
    add dx, BZ_PLH
    cmp dx, [bz_pwy]
    jle .no
    call bz_pxwin
    jnc .no
    pop dx
    stc
    ret
.no:
    pop dx
    clc
    ret

; CF = 1 when the slab's columns meet the window's (bz_pwc).  Preserves all
; but the flags.
bz_pxwin:
    push ax
    push dx
    mov ax, [bz_pwc]
    shl ax, 1
    shl ax, 1
    shl ax, 1
    mov dx, [bz_pox]
    add dx, BZ_PLW
    cmp dx, ax
    jle .no
    mov ax, [bz_pwc]
    add ax, [bz_W]
    shl ax, 1
    shl ax, 1
    shl ax, 1
    cmp [bz_pox], ax
    jge .no
    pop dx
    pop ax
    stc
    ret
.no:
    pop dx
    pop ax
    clc
    ret

; AX = the shown slab's line: CF = 1 when it is NEAR the window's edge ON THE
; BALL'S SIDE (128.12.7: within two card rows of its top or bottom, a word
; column of its left or right - the top only while the ball's footprint is in
; the window's upper half, the bottom only in its lower half, the left only
; in its left half, the right only in its right half: GLIDE pans toward the
; ball, so a strip can enter only on that side), so an entering strip may
; meet it.  Preserves all but the flags.
bz_pnear:
    push ax
    push cx
    push dx
    push ax
    xor cx, cx                  ; CL bit 0: the ball's upper half, bit 1 its
    mov dx, [bz_py]             ; left (2 x its centre against 2 x the
    shl dx, 1                   ; window's)
    add dx, BZ_BAL_ROWS
    mov ax, [bz_pwy]
    shl ax, 1
    add ax, BZ_LINES
    cmp dx, ax
    jge .lr
    or cl, 1
.lr:
    mov dx, [bz_px]
    and dl, 0fch
    shl dx, 1
    add dx, BZ_FOOTW
    mov ax, [bz_pwc]
    shl ax, 1
    add ax, [bz_W]
    shl ax, 1
    shl ax, 1
    shl ax, 1
    cmp dx, ax
    jge .side
    or cl, 2
.side:
    pop ax
    mov dx, [bz_rl]
    shl dx, 1                   ; two card rows
    test cl, 1
    jz .bot
    add dx, [bz_pwy]
    cmp ax, dx
    jl .yes
    jmp short .x
.bot:
    neg dx
    add dx, [bz_pwy]
    add dx, BZ_LINES
    add ax, BZ_PLH
    cmp ax, dx
    jg .yes
.x:
    test cl, 2
    jz .rt
    mov ax, [bz_pwc]
    inc ax
    shl ax, 1
    shl ax, 1
    shl ax, 1
    cmp [bz_pox], ax
    jl .yes
    jmp short .no
.rt:
    mov ax, [bz_pwc]
    add ax, [bz_W]
    dec ax
    shl ax, 1
    shl ax, 1
    shl ax, 1
    mov dx, [bz_pox]
    add dx, BZ_PLW
    cmp dx, ax
    jg .yes
.no:
    clc
    jmp short .out
.yes:
    stc
.out:
    pop dx
    pop cx
    pop ax
    ret

; bz_pedge - THE EDGE CLAUSE's facts (SPEC.md 128.12.7), the window as it
; stands before the camera (asked only where they are read: a contact lane's
; frame, and a heavy one's camera): bz_hedr = 1 when the ball's new footprint is within
; BZ_HEDGE lines of its top or bottom, bz_hedc = 1 within 24 px of its left or
; right.  A hidden ball (bz_tube) has no footprint and releases both (the
; ghost's GLIDE).  Clobbers DX.
bz_pedge:
    push ax
    mov word [bz_hedr], 0101h
    cmp byte [bz_tube], 0
    jne .out
    mov word [bz_hedr], 0
    mov ax, [bz_py]
    mov dx, [bz_pwy]
    add dx, BZ_HEDGE
    cmp ax, dx
    jl .r
    add ax, BZ_BAL_ROWS
    add dx, BZ_LINES - 2 * BZ_HEDGE
    cmp ax, dx
    jle .c
.r:
    mov byte [bz_hedr], 1
.c:
    mov dx, [bz_c0]
    shl dx, 1
    shl dx, 1
    shl dx, 1                   ; DX = the window's left px
    mov ax, [bz_px]
    and al, 0fch
    add dx, 24
    cmp ax, dx
    jl .cc
    add ax, BZ_FOOTW
    mov dx, [bz_c0]
    add dx, [bz_W]
    shl dx, 1
    shl dx, 1
    shl dx, 1
    sub dx, 24                  ; ...its right less 24
    cmp ax, dx
    jle .out
.cc:
    mov byte [bz_hedc], 1
.out:
    pop ax
    ret

; -> AL nonzero (ZF = 0) when this frame runs the OCCLUDER PASS: the centre's
; cell has OCC airborne or OCCG grounded, or a harness poked the ball (bz_mkboxes's
; gate, SPEC.md 128.11.10.2).  Clobbers AX.
bz_passon:
    mov ah, BZ_FOCC
    cmp byte [bz_air], 0
    jne .a
    mov ah, BZ_FL_OCCG
.a:
    mov al, [bz_nbr + BZN_C + 3]
    and al, ah
    or al, [bz_pokd]
    ret

; CF = 1 when a contact LANE may be drawn this frame (SPEC.md 128.12.4.3): no
; occluder pass, the ball's new footprint outside the edge zone, and the
; ball's and the shadow's footprints - old and new - ONE box between them
; (bz_union's BZ_BOXW x BZ_BOXH), so the contact frame is at most two boxes.
; A hidden ball's frame has none of these.  Clobbers AX, BX, SI.
bz_conok:
    cmp byte [bz_tube], 0
    jne .yes
    call bz_pedge
    call bz_passon
    jnz .no
    cmp word [bz_hedr], 0
    jne .no
    mov si, bz_ur               ; the union, from the ball's new footprint
    mov ax, [bz_nfx0]
    mov [si], ax
    mov ax, [bz_nfx1]
    mov [si + 2], ax
    mov ax, [bz_nfy0]
    mov [si + 4], ax
    mov ax, [bz_nfy1]
    mov [si + 6], ax
    cmp byte [bz_oldv], 0
    je .ns
    mov bx, bz_ofx0
    call bz_union
    jc .no
    cmp byte [bz_sov], 0
    je .ns
    mov bx, bz_sox0
    call bz_union
    jc .no
.ns:
    cmp byte [bz_shc], 0
    je .yes
    mov bx, bz_snx0
    call bz_union
    jc .no
.yes:
    stc
    ret
.no:
    clc
    ret

; CF = 1 when a frame with no contact group is HEAVY at level 1 (SPEC.md
; 128.12.7): it runs the occluder pass, its ball's group is TWO boxes (its old
; and new footprints do not fit one, unclipped), or it shows the slab near the
; window's edge.  A hidden ball's is not.  Clobbers AX, BX, SI.
bz_hv1:
    cmp byte [bz_tube], 0
    jne .no
    test byte [bz_pflag], 2
    jnz .yes
    call bz_passon
    jnz .yes
    cmp byte [bz_oldv], 0
    je .no
    mov si, bz_nfx0
    mov bx, bz_ofx0
    call bz_union               ; (CF = 1: two boxes)
    ret
.yes:
    stc
    ret
.no:
    clc
    ret

; -----------------------------------------------------------------------------
; bz_hvcam - THE HEAVY FRAME in GLIDE (SPEC.md 128.12.7, bbcourse.Glide's
; heavy branch), after its step is clamped: level 2 withholds every row and
; the column, level 1 all rows but one and the column; each axis is released
; when bz_props found the ball's new footprint near that edge.  A withheld
; column keeps the pan on at its old parity, a withheld row keeps the y pan
; on: the next light frame takes them.  Counts bz_nhvy, bz_nhedge, bz_nwc,
; bz_nwr.  Clobbers AX, BX, CX, DX.
; -----------------------------------------------------------------------------
bz_hvcam:
    mov al, [bz_heavy]
    or al, al
    jz .out
    inc word [bz_nhvy]
    mov ah, [bz_hedr]
    or ah, [bz_hedc]
    jz .col
    inc word [bz_nhedge]
.col:
    cmp byte [bz_hedc], 0
    jne .rows
    mov dx, [bz_c0]
    cmp dx, [bz_c0n]
    je .rows
    mov [bz_c0n], dx
    inc word [bz_nwc]
    mov byte [bz_gpx], 1
    mov ah, [bz_kpar]
    mov [bz_gpar], ah
.rows:
    cmp byte [bz_hedr], 0
    jne .out
    mov dx, [bz_R0n]
    sub dx, [bz_R0]             ; DX = the step, d
    mov cx, 1                   ; CX = the rows allowed: 1, or 0 at level 2
    cmp al, 2
    jne .lim
    dec cx
.lim:
    mov bx, dx
    sub bx, cx
    jle .lo
    add [bz_nwr], bx            ; d - lim withheld
    mov dx, cx
    jmp short .set
.lo:
    mov bx, dx
    add bx, cx
    jge .out
    neg bx
    add [bz_nwr], bx            ; -lim - d withheld
    mov dx, cx
    neg dx
.set:
    add dx, [bz_R0]
    mov [bz_R0n], dx
    mov byte [bz_gpy], 1
.out:
    ret

; bz_hspin - a harness's LATE FRAME (bz_hold, SPEC.md 128.12.5.6): a spin on
; the clock for bz_hold x 256 PIT counts, then bz_hold = 0.  Preserves all but
; the flags.
bz_hspin:
    push ax
    push bx
    push cx
    push dx
    call bz_clk_sample
    mov bx, [bz_subs]
    mov cx, [bz_pitl]
.l:
    call bz_clk_sample
    call bz_elap
    or dx, dx
    jnz .d
    cmp ah, [bz_hold]
    jb .l
.d:
    mov byte [bz_hold], 0
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; =============================================================================
; THE SLAB ON THE CARD (SPEC.md 128.12.4.3, 128.12.4.5, 128.12.6.4).  The
; platform is not in the map: every box that meets its drawn footprint
; (bz_pline) is composed with it - under the ball, or over it by ONE decision a
; frame (bz_povr) - and three things put it on the card: its BOX when its drawn
; line changes while it is shown (bz_props's contact, bz_cslab), its box after
; a FULL WRITE (bz_pfull), and its box CLIPPED to the cells a strip brings in
; (bz_pstrip).  Nothing else writes it, so nothing else needs to know.
; =============================================================================
BZ_PLB      equ BZ_PLW / 4      ; the slab's bytes a line (4 px a byte)
%if BZ_PLSPR != 4 * BZ_PLH * BZ_PLB || (BZ_PLH & 1) || BZ_PLB != 2 * BZ_BOXW
 %error "the slab's sprite: two parity copies of an 18-line mask and frame, a box wide (SPEC.md 128.12.6.4)"
%endif

; bz_pfull - a FULL WRITE's slab, after bz_lfull: the write puts the course
; alone on the card, so a slab SHOWN in the new window is drawn by its box
; after it (a full write's boxes follow it, 128.12.6.4), and one outside it
; follows n in RAM (128.12.15 item 3).  Preserves nothing.
bz_pfull:
    mov bl, [bz_pidx]
    cmp bl, 0ffh
    je .out
    xor bh, bh
    mov ax, [bz_R0n]
    mov cl, [bz_lsh]
    shl ax, cl
    mov [bz_pwy], ax
    mov ax, [bz_c0n]
    mov [bz_pwc], ax
    call bz_ptrue
    call bz_pshown
    jc .box
    mov [bz_pline], ax
.out:
    ret
.box:
    call bz_cslab               ; (bz_pline 8000h: its true footprint alone)
    inc word [bz_ncon]
    ret

; bz_pstrip - A STRIP MEETING THE SLAB (SPEC.md 128.12.4.3), after the camera
; (the strips are its), bz_wtop set: the entering rows and column bring course
; cells from the map, which does not hold the slab.  On a frame whose slab box
; was not chosen, the slab's box CLIPPED to those cells - the bounding rect of
; its footprint's meets with the rows and with the column, inside the
; footprint and so one box - is the contact group (bz_ctype 3).  A contact
; LANE yields it the slot: its map words go back to its drawn pose and it
; waits (display only, 128.12.5.2) - a post LIGHTING too, a frame late; a
; must-draw rotor cannot meet this case (the tool keeps a windmill and a
; track out of one window, 128.12.4.6), and there the slab's strip cells
; wait for its next box.  It does not feed
; bz_heavy (128.12.7: the slab NEAR the edge does).  Clobbers AX, BX, CX, DX.
bz_pstrip:
    cmp byte [bz_pidx], 0ffh
    je .out
    cmp byte [bz_full], 0
    jne .out
    cmp byte [bz_ctype], 2      ; its box: the whole footprint, drawn and true
    je .out                     ; (its own group, or beside a post's)
    test byte [bz_pflag], 4
    jnz .out
    cmp word [bz_pline], BZ_PLNONE
    je .out
    mov ax, [bz_dr]
    or ax, [bz_dc]
    jnz .go
.out:
    ret
.go:
    mov byte [bz_pany], 0
    mov ax, [bz_pox]            ; the footprint, words x lines inclusive
    mov cl, 3
    shr ax, cl
    mov [bz_lrc], ax
    add ax, BZ_BOXW - 1
    mov [bz_lrc + 2], ax
    mov ax, [bz_pline]
    mov [bz_lrc + 4], ax
    add ax, BZ_PLH - 1
    mov [bz_lrc + 6], ax
    mov ax, [bz_dr]             ; THE ROWS: the new window's bottom dr (top -dr)
    or ax, ax
    jz .col
    mov cl, [bz_lsh]
    mov bx, [bz_wtop]
    jns .down
    neg ax
    shl ax, cl                  ; -dr rows' lines:
    mov cx, bx                  ; [top, top + lines - 1]
    mov dx, bx
    add dx, ax
    dec dx
    jmp short .rows
.down:
    shl ax, cl                  ; dr rows' lines:
    mov dx, bx                  ; [top + LINES - lines, top + LINES - 1]
    add dx, BZ_LINES - 1
    mov cx, bx
    add cx, BZ_LINES
    sub cx, ax
.rows:
    mov ax, [bz_c0n]
    mov bx, ax
    add bx, [bz_W]
    dec bx
    call bz_pmeet
.col:
    mov ax, [bz_dc]             ; THE COLUMN: the new window's left (right)
    or ax, ax
    jz .done
    mov ax, [bz_c0n]
    js .left
    add ax, [bz_W]
    dec ax
.left:
    mov bx, ax
    mov cx, [bz_wtop]
    mov dx, cx
    add dx, BZ_LINES - 1
    call bz_pmeet
.done:
    cmp byte [bz_pany], 0
    je .out
    cmp byte [bz_ctype], 1
    jne .take
    cmp byte [bz_must], 0       ; (a must-draw ROTOR keeps the slot - bz_must
    jne .out                    ; is one only when it was chosen; a post
                                ; lighting yields it as a contact lane does
                                ; and lights next frame, its lit frames
                                ; counted only once it is on the glass)
    mov bl, [bz_cln]            ; a contact lane waits: its drawn pose back
    xor bh, bh
    mov al, [bz_cold]
    call bz_lsync
    mov al, [bz_cage]
    mov [bz_lage + bx], al
    inc word [bz_ndef]
    dec word [bz_ncon]
.take:
    mov ax, [bz_prc]
    mov [bz_crect], ax
    mov ax, [bz_prc + 2]
    mov [bz_crect + 2], ax
    mov ax, [bz_prc + 4]
    mov [bz_crect + 4], ax
    mov ax, [bz_prc + 6]
    mov [bz_crect + 6], ax
    mov byte [bz_ctype], 3
    inc word [bz_ncon]
    inc word [bz_npbx]
    ret

; AX = x0, BX = x1 (words), CX = y0, DX = y1 (lines), inclusive: a strip's meet
; with the slab's footprint (bz_lrc), unioned into bz_prc (bz_pany 1 once one
; is found).  Clobbers AX, BX, CX, DX.
bz_pmeet:
    cmp ax, [bz_lrc]
    jge .a
    mov ax, [bz_lrc]
.a:
    cmp bx, [bz_lrc + 2]
    jle .b
    mov bx, [bz_lrc + 2]
.b:
    cmp ax, bx
    jg .no
    cmp cx, [bz_lrc + 4]
    jge .c
    mov cx, [bz_lrc + 4]
.c:
    cmp dx, [bz_lrc + 6]
    jle .d
    mov dx, [bz_lrc + 6]
.d:
    cmp cx, dx
    jg .no
    cmp byte [bz_pany], 0
    jne .u
    mov byte [bz_pany], 1
    mov [bz_prc], ax
    mov [bz_prc + 2], bx
    mov [bz_prc + 4], cx
    mov [bz_prc + 6], dx
    ret
.u:
    cmp ax, [bz_prc]
    jge .u1
    mov [bz_prc], ax
.u1:
    cmp bx, [bz_prc + 2]
    jle .u2
    mov [bz_prc + 2], bx
.u2:
    cmp cx, [bz_prc + 4]
    jge .u3
    mov [bz_prc + 4], cx
.u3:
    cmp dx, [bz_prc + 6]
    jle .no
    mov [bz_prc + 6], dx
.no:
    ret

; bz_povr - the slab's ONE DECISION a frame (SPEC.md 128.12.4.5): bz_pov FFh
; when no slab is on the card, else 1 - OVER the ball - when
;     z_b + m < its top   and   s_b <= sP
; (z_b the ball's whole px, m BZ_CLIMB grounded and 0 airborne, as the
; occluder rule's; its top hP + I at the DRAWN line, hP + poy - line; sP its
; shaft's cell row Awx + Awy, bbcourse.slab_s), and 0 under it.  A hidden ball
; draws nothing, so under.  Clobbers AX, CX.
bz_povr:
    mov byte [bz_pov], 0ffh
    cmp byte [bz_pidx], 0ffh
    je .out
    mov ax, [bz_pline]
    cmp ax, BZ_PLNONE
    je .out
    mov byte [bz_pov], 0
    cmp byte [bz_tube], 0
    jne .out
    mov cx, [bz_poy]            ; its top: hP + poy - line
    sub cx, ax
    add cx, [bz_php]
    mov ax, [bz_psa]            ; sP
    cmp [bz_sb], ax
    jg .out
    mov ax, [bz_gz + 1]         ; z_b + m
    cmp byte [bz_air], 0
    jne .a
    add ax, BZ_CLIMB
.a:
    cmp ax, cx
    jge .out
    mov byte [bz_pov], 1
.out:
    ret

; bz_pover - after the occluder pass: the slab OVER the ball (bz_pov 1) laid
; into every box it meets, last (128.12.4.5's order).  Preserves nothing.
bz_pover:
    cmp byte [bz_pov], 1
    jne .out
    push ds
    pop es
    mov si, bz_boxes
    mov cx, [bz_nbox]
    jcxz .out
.b:
    push cx
    call bz_pblit
    pop cx
    add si, BZ_BOXD
    loop .b
.out:
    ret

; bz_pblit - THE SLAB at its drawn line (bz_pline) into box SI, clipped to it:
; parity copy (bz_pline AND 1) of its sprite - the Hercules's mid level is a
; checker tied to the line, so the fetch translated copy p's row r through
; table (p + r) AND 1 (bonanza.asm bz_hxlat) - mask AND, frame OR, BZ_PLB bytes
; a line from world byte bz_pox / 4 (a 16 px column: no shift).  The mask and
; the frame are read through the course part's own segment.  DS = ES = ours.
; Preserves all but AX, BX, CX, DX, DI, BP.
bz_pblit:
    push si
    mov ax, [bz_pline]
    mov cx, [si + 2]            ; rows i in [imin, imax): pline + i in the box
    sub cx, ax
    jge .i0
    xor cx, cx
.i0:
    mov dx, [si + 2]
    add dx, [si + 6]
    sub dx, ax
    cmp dx, BZ_PLH
    jle .i1
    mov dx, BZ_PLH
.i1:
    sub dx, cx                  ; DX = the rows, CX = imin
    jle .out
    mov bx, [bz_pox]
    shr bx, 1
    shr bx, 1                   ; BX = the slab's first world byte
    mov ax, [si]                ; bytes k in [kmin, kmax): bx + k in the box
    shl ax, 1
    sub ax, bx
    jge .k0
    xor ax, ax
.k0:
    mov bp, [si]
    add bp, [si + 4]
    shl bp, 1
    sub bp, bx
    cmp bp, BZ_PLB
    jle .k1
    mov bp, BZ_PLB
.k1:
    sub bp, ax                  ; BP = the bytes a row, AX = kmin
    jle .out
    mov di, [bz_pline]          ; the destination: buf + (pline + imin - y0) 8
    add di, cx                  ; + (bx + kmin - 2 x0)
    sub di, [si + 2]
    shl di, 1
    shl di, 1
    shl di, 1
    add di, [si + 8]
    add di, bx
    add di, ax
    mov bx, [si]
    shl bx, 1
    sub di, bx
    mov si, cx                  ; the source: the copy's mask + 8 imin + kmin
    shl si, 1
    shl si, 1
    shl si, 1
    add si, ax
    add si, [bz_pspr]
    test byte [bz_pline], 1
    jz .p0
    add si, 2 * BZ_PLH * BZ_PLB
.p0:
    cmp bp, BZ_PLB              ; WHOLE ROWS (the slab's own box, the ball's
    jne .bytes                  ; box riding it at the same columns): the
    mov cx, dx                  ; buffer's and the sprite's lines are both 8
    shl cx, 1                   ; bytes, so the rows are ONE run of words,
    push ds                     ; two an iteration - half the byte path's
    mov ds, [bz_cseg]           ; clocks
.w:
    lodsw
    and ax, [es:di]
    or ax, [si + BZ_PLH * BZ_PLB - 2]
    stosw
    lodsw
    and ax, [es:di]
    or ax, [si + BZ_PLH * BZ_PLB - 2]
    stosw
    loop .w
    pop ds
    jmp short .out
.bytes:
    mov cx, bp
    mov bx, BZ_BOXW * 2
    sub bx, cx                  ; BX = the buffer's step after a row's bytes
    mov bp, BZ_PLB
    sub bp, cx                  ; BP = the sprite's
    push ds
    mov ds, [bz_cseg]
.r:
    push cx
.b:
    lodsb                       ; the mask (a set bit keeps the box)...
    and al, [es:di]
    or al, [si + BZ_PLH * BZ_PLB - 1] ; ...and the frame, BZ_PLH rows on
    stosb
    loop .b
    pop cx
    add si, bp
    add di, bx
    dec dx
    jnz .r
    pop ds
.out:
    pop si
    ret
