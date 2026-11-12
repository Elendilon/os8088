; bzgame.inc - BONANZA's frame loop, simulation, camera, autopilot and
; instruments (SPEC.md 128.4 - 128.6).
;
; =============================================================================
; GUEST STATE A HARNESS READS (tests/bonanza_*.py; offsets are the package
; segment's, resolved through the listing or a re-assembly like Excitebike's)
; =============================================================================
;   bz_mode     byte   0 play, 1 benchmark (B)
;   bz_fs       byte   1 while the bracket is up (mode set .. the loop's end)
;   bz_err      byte   0; 1 the mode was refused; 2 the display changed under us
;   bz_herc     byte   0 CGA, 1 Hercules
;   bz_S        word   the SHOWN start address, words, < 4096: (W*bz_R0 + bz_c0)
;                      mod 4096, written by bz_flip at bz_tf in the same frame
;   bz_R0       word   the shown window's top CARD row (2 lines CGA, 4 Hercules)
;   bz_c0       word   ...and its left WORD column (8 game px)
;   bz_bx,bz_by DWORD  the ball's top-left, world px in 24.8 fixed point:
;                      +0 the fraction byte, +1 the integer px as a WORD,
;                      +3 always 0.  (16 px margin: 16..480 x 16..1568.)
;   bz_px,bz_py word   the integer px this frame drew the ball at (= the word at
;                      bz_bx+1 / bz_by+1 when the frame began its boxes)
;   bz_frm      word   the ball frame drawn: ((py & 7) * 8 + (px & 7))
;   bz_vx,bz_vy word   velocity, signed, 1/256 px a step
;   bz_frames   word   frames presented this bracket (bz_presented counts)
;   bz_mfr      word   ...of which MEASURED (a benchmark's frames but a full
;                      write; play measures nothing)
;   bz_ncol     word   columns written (a column split round the boxes calls
;                      bz_col twice and counts once); bz_nrow word bz_row
;                      calls; bz_nfull word full writes; bz_tos word
;                      retrace-wait timeouts
;   bz_miss     word   measured frames whose period passed 1.5 refreshes (a
;                      missed retrace: the frame showed for two or more)
;   bz_fmax     DWORD  the longest measured frame period, PIT counts
;   bz_acc      6 DWORDS, PIT counts summed over the measured frames, one per
;                      part: 0 sim+camera (bz_t0..bz_ts), 1 box compose
;                      (..bz_tr), 2 rows (..bz_tv), 3 retrace wait, IDLE
;                      (..bz_tf), 4 flip + columns (..bz_tb, and bz_tc ..
;                      bz_presented), 5 box write (bz_tb..bz_tc, or
;                      ..bz_presented when no column rows follow the boxes).
;                      CPU clocks = counts x 4.
;   bz_cmode    byte   the camera MODE (SPEC.md 128.9): 0 GLIDE, 1 FOLLOW, 2
;                      TRICKLE.  C cycles it, in play and on the desktop; it
;                      persists across plays (bss, never reset).  The benchmark
;                      runs GLIDE whatever it says and leaves it alone
;   bz_late     word   frames with a box at window row 0 whose box did not
;                      START before the beam reached window line 0 (the column
;                      rows down to the box's last line went first) or did not
;                      END before it reached the box's last line (SPEC.md
;                      128.9 item 6, bz_latechk): 0 over the benchmark is what
;                      bonanzaring asserts
;   bz_res      byte   1 = the bz_r* copy below holds a finished benchmark
;   bz_rframes, bz_rmfr, bz_rncol, bz_rnrow, bz_rnfull, bz_rmiss, bz_rfmax,
;                      bz_racc, bz_rlate: that copy, the same layout as
;                      bz_frames .. bz_late
;
; AT bz_presented THE CARD HOLDS THE WINDOW EXACTLY: every word of the W x H
; window at bz_S is the course's, with the ball at (bz_px, bz_py) composited
; (frame bz_frm, shift bz_px & 3).  bonanzaring decodes it there.
;
; THE FRAME (SPEC.md 128.4), marks as GLOBAL labels in this order:
;   bz_t0 .. bz_ts .. bz_tr .. bz_tv .. bz_tf .. bz_tb [.. bz_tc] ..
;   bz_presented
; and bz_col / bz_row (bzvideo.inc) are the writers' entries.  bz_tc runs only
; on a frame whose entering column is SPLIT round the boxes (bz_csplit): the
; column's rows above the boxes' top row go between bz_tf and bz_tb, the boxes
; between bz_tb and bz_tc, and the column's remaining rows between bz_tc and
; bz_presented - raster order, so neither the column nor the box races the
; beam (SPEC.md 128.2 rule 4 as amended by the wave-0 fix stage).  A box at
; window row 0 has no column rows above it: then the column's rows down to the
; boxes' LAST row go first, the boxes, and the rest (SPEC.md 128.9 item 6).
;
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
BZ_ACC      equ 8               ; an arrow's acceleration, 1/256 px a step a step
BZ_VMAX     equ 512             ; |v| at most 2 px a step: 16 px a frame at 8 steps,
                                ; which is what keeps an old+new footprint union
                                ; inside one BZ_BOXW x BZ_BOXH box at full rate
BZ_REACH    equ 12              ; the autopilot's waypoint radius, px
BZ_KSC_F    equ 21h             ; the F key's make code
BZ_KSC_B    equ 30h             ; ...and B's
BZ_KSC_C    equ 2eh             ; ...and C's: the camera mode (SPEC.md 128.9)
BZ_CMODES   equ 3               ; GLIDE, FOLLOW, TRICKLE
; GLIDE's "faster than 4 px (x) / 2 lines (y) a FRAME" as |v| in 1/256 px a
; STEP: a frame runs 54.62 / refresh steps on average (FASTTICK's 1,193,182 /
; 21,845 Hz against 128.8's 59.92 Hz CGA and 50.85 Hz Hercules refresh: 0.9115
; and 1.0741), so the ball passes 4 px a frame past |v| = 1024 / that and 2
; lines past 512 / that.  With wave 0's BZ_VMAX of 512 the x pair is out of
; reach on both cards (GLIDE pans one column every second frame, 4 px a frame,
; about twice the ball's top speed) and the y pair is reached on the Hercules
; only; later waves' physics may cross them.
BZ_GFXC     equ 1124            ; CGA, x: 1024 / 0.9115 = 1123.4
BZ_GFXH     equ 954             ; Hercules, x: 1024 / 1.0741 = 953.4
BZ_GFYC     equ 562             ; CGA, y: 512 / 0.9115 = 561.7
BZ_GFYH     equ 477             ; Hercules, y: 512 / 1.0741 = 476.7
BZ_K_L      equ 1               ; bz_keys: the arrows held
BZ_K_R      equ 2
BZ_K_U      equ 4
BZ_K_D      equ 8
BZ_LIVE     equ 42              ; bytes of bz_frames .. bz_late (the results copy)

%macro BZ_GAME_VARS 0
VAR bz_mode,1
VAR bz_fs,1
VAR bz_err,1
VAR bz_herc,1
VAR bz_res,1
VAR bz_full,1
VAR bz_meas,1
VAR bz_first,1
VAR bz_oldv,1
VAR bz_keys,1
VAR bz_lsh,1
VAR bz_row0,1                   ; 1: this frame's box is at window row 0 (bz_csplit)
VAR bz_vedge,1                  ; 1: bz_vr saw the sync RISE (not already high)
VAR bz_pad0,1                   ; (the words below stay even)
VAR bz_cmode,1                  ; the camera mode: 0 GLIDE, 1 FOLLOW, 2 TRICKLE
VAR bz_cuse,1                   ; ...the one this frame used (a benchmark: GLIDE)
VAR bz_ckey,1                   ; FFh while C was down last frame (the edge)
VAR bz_gpx,1                    ; GLIDE: 1 while the x pan is on
VAR bz_gpy,1                    ; ...the y pan
VAR bz_gpar,1                   ; ...the x pan's frame parity (0: step now)
VAR bz_gdx,1                    ; ...the ball's last x direction: 0 right, 1 left
VAR bz_gdy,1                    ; ...and y: 0 down, 1 up
VAR bz_gfx,2                    ; ...BZ_GFX? and BZ_GFY? for this card
VAR bz_gfy,2
VAR bz_lbx,2                    ; FOLLOW: the low words of last frame's bz_bx,
VAR bz_lby,2                    ; bz_by (24.8: the frame's travel)
VAR bz_fvx,2                    ; ...the camera velocity, 1/256 px (line) a frame
VAR bz_fvy,2
VAR bz_fcx,4                    ; ...its position, 24.8 like bz_bx: the window's
VAR bz_fcy,4                    ; left px and top line, + 1 the integer word
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
VAR bz_rframes,2
VAR bz_rmfr,2
VAR bz_rncol,2
VAR bz_rnrow,2
VAR bz_rnfull,2
VAR bz_rmiss,2
VAR bz_rfmax,4
VAR bz_racc,4 * BZ_NPART
VAR bz_rlate,2
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
VAR bz_cfrom,2
VAR bz_crest,2
VAR bz_cbot,2                   ; the boxes' lowest window line (bz_csplit)
; the footprints and the boxes
VAR bz_ofx0,2
VAR bz_ofx1,2
VAR bz_ofy0,2
VAR bz_ofy1,2
VAR bz_nfx0,2
VAR bz_nfx1,2
VAR bz_nfy0,2
VAR bz_nfy1,2
VAR bz_nbox,2
VAR bz_opx,2                    ; the ball's px, py last frame (the idle test)
VAR bz_opy,2
VAR bz_xhi,2                    ; the second box's overlap band (bz_boxw)
VAR bz_xlo,2
VAR bz_xa,2
VAR bz_xb,2
VAR bz_xact,2
VAR bz_bw,2
VAR bz_bstep,2                  ; bz_boxw: buffer step from a line's end to the next
VAR bz_wtab,10                  ; W * dr for dr = -2 .. 2 (bz_tf's incremental S)
VAR bz_bx2,2
VAR bz_imin,2
VAR bz_fmp,2                    ; bz_boxc's fill: the run's map entry, buffer
VAR bz_fbp,2                    ; line, line word in a block, lines left
VAR bz_flo,2
VAR bz_fln,2
VAR bz_kmin,2
VAR bz_boxes,2 * BZ_BOXD
VAR bz_boxbuf,2 * BZ_BOXB
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
; bz_latechk - SPEC.md 128.9 item 6, the box at window row 0: CF = 1 if NOW is
; later than the beam reaching window line AX.  The beam is reckoned from the
; retrace wait's last clock sample ([bz_vsubs], [bz_vpit]): when the wait saw
; the sync RISE ([bz_vedge]) that is its start, less a line for the loop, so
; 15 lines of sync are still to come; when the sync was already high it may
; have been anywhere in its 16 lines, and its END is the late case.  Then
; [bz_lblank] counts of blank and AX window lines (76 counts a CGA line, 63 a
; Hercules one; both round toward LATE).  Preserves all but the flags.
; -----------------------------------------------------------------------------
bz_latechk:
    push ax
    push bx
    push cx
    push dx
    cmp byte [bz_vedge], 0
    je .lv
    add ax, 15                  ; the sync's lines still to come
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
; bz_play - the frame loop, until Esc / F / Alt+Enter or the benchmark's last
; frame.  DS = ours, the mode set, bz_vinit run.
; -----------------------------------------------------------------------------
bz_play:
    call bz_drain               ; what the launching key typed is not a command
    mov word [bz_bx], (BZ_START_X << 8) & 0ffffh
    mov word [bz_bx + 2], BZ_START_X >> 8
    mov word [bz_by], (BZ_START_Y << 8) & 0ffffh
    mov word [bz_by + 2], BZ_START_Y >> 8
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
    mov di, bz_frames
    mov cx, BZ_LIVE / 2
    rep stosw
    mov word [bz_wp], 1         ; waypoint 0 is the start
    mov byte [bz_first], 1
    mov byte [bz_ckey], 0ffh    ; C must go down IN play to count (an edge)
    cmp byte [bz_mode], 0
    je .play
    mov byte [bz_res], 0        ; a benchmark replaces the last one's results
.play:
    call bz_clk_sample
    mov ax, [bz_subs]
    mov [bz_lsubs], ax
    mov [bz_msubs], ax
    mov ax, [bz_pitl]
    mov [bz_mpit], ax
bz_t0:
    call bz_exitchk
    jnc .on
    ret
.on:
    cmp byte [bz_mode], 0
    jne .steps
    call bz_input               ; play: the arrows, once a frame
.steps:
    mov cx, [bz_subs]           ; (sampled at the last frame's end mark)
    sub cx, [bz_lsubs]
    add [bz_lsubs], cx
    cmp cx, BZ_STEPS
    jbe .n
    mov cx, BZ_STEPS
.n:
    jcxz .camera
.step:
    call bz_step
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
    call bz_boxc
    add si, BZ_BOXD
    loop .comp
bz_tr:
    mov bx, 1 * 4
    call bz_mark
    cmp byte [bz_full], 0
    jne bz_tv
    call bz_rows
bz_tv:
    mov bx, 2 * 4
    call bz_mark
    cmp byte [bz_full], 0
    jne bz_tf
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
    mov word [bz_crest], 0      ; no column rows left for after the boxes
    mov byte [bz_row0], 0       ; ...and no box at row 0 to time
    cmp byte [bz_full], 0
    je .col
    call bz_fullw
    jmp bz_tb
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
    call bz_csplit              ; CX = the column's rows that go BEFORE the boxes
    mov [bz_cfrom], cx
    mov dx, [bz_H]
    sub dx, cx
    mov [bz_crest], dx          ; ...and the rows after them
    jcxz bz_tb
    mov ax, [bz_ccol]           ; (bz_csplit spent AX)
    xor bx, bx                  ; from the window's top row
    call bz_col
bz_tb:
    mov bx, 4 * 4
    call bz_mark
    cmp byte [bz_row0], 0       ; A BOX AT WINDOW ROW 0 (SPEC.md 128.9 item 6):
    je .go                      ; the column's rows down to its last line went
    xor ax, ax                  ; first (they outrun the beam), so they and the
    call bz_latechk             ; box's first line are on time if the box
    rcl byte [bz_row0], 1       ; starts before the beam reaches line 0 (2 or 3)
.go:
    mov bx, 5 * 4               ; (the part the next mark closes: the box write)
    mov si, bz_boxes
    mov cx, [bz_nbox]
    jcxz .wrote
.write:
    call bz_boxw
    add si, BZ_BOXD
    loop .write
.wrote:
    cmp byte [bz_row0], 0       ; ...and its LAST line if the box is done before
    je .timed                   ; the beam reaches that: a writer at a steady
    mov ax, [bz_cbot]           ; speed is ahead of the beam at every line
    call bz_latechk             ; between if it is at both ends
    adc byte [bz_row0], 0
    cmp byte [bz_row0], 2
    je .timed
    inc word [bz_late]          ; late at either end: counted, and finished
.timed:
    cmp word [bz_crest], 0
    je bz_presented
bz_tc:
    call bz_mark                ; BX = 5*4: the box write ends here
    mov ax, [bz_ccol]           ; the column's rows under the boxes' last row
    mov bx, [bz_cfrom]
    mov cx, [bz_crest]
    call bz_col
    mov bx, 4 * 4               ; ...which are the flip+columns part's
bz_presented:
    call bz_mark
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
    mov ax, [bz_nfx0]           ; the footprint drawn is the next frame's old one
    mov [bz_ofx0], ax
    mov ax, [bz_nfx1]
    mov [bz_ofx1], ax
    mov ax, [bz_nfy0]
    mov [bz_ofy0], ax
    mov ax, [bz_nfy1]
    mov [bz_ofy1], ax
    mov byte [bz_oldv], 1
    cmp byte [bz_mode], 0
    je .next
    cmp word [bz_frames], BZ_BENCH
    jb .next
    push ds                     ; the benchmark is done: its results stay
    pop es                      ; for the desktop
    mov si, bz_frames
    mov di, bz_rframes
    mov cx, BZ_LIVE / 2
    rep movsw
    mov byte [bz_res], 1
    ret
.next:
    jmp bz_t0

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

; the arrows held -> [bz_keys], and C's key-down EDGE (not its repeat) cycles
; the camera mode (SPEC.md 128.9).  Preserves all but the flags.
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
    jnc .out
    or bl, BZ_K_D
.out:
    mov [bz_keys], bl
    pop bx
    pop ax
    ret

; the next camera mode, GLIDE -> FOLLOW -> TRICKLE -> GLIDE.  Preserves all
; but the flags.  The camera picks its new state up itself (bz_camera's tail).
bz_cnext:
    inc byte [bz_cmode]
    cmp byte [bz_cmode], BZ_CMODES
    jb .out
    mov byte [bz_cmode], 0
.out:
    ret

; -----------------------------------------------------------------------------
; bz_step - one fixed simulation step (SPEC.md 128.5, wave 0): the arrows (or
; the autopilot's) accelerate, a drag acts always, the course's edges reflect
; with a restitution of one half.  Preserves all but the flags.
; -----------------------------------------------------------------------------
bz_step:
    push ax
    push bx
    push dx
    mov bl, [bz_keys]
    cmp byte [bz_mode], 0
    je .keys
    call bz_auto                ; the benchmark: BL = the keys it would hold
.keys:
    mov ax, [bz_vx]
    test bl, BZ_K_L
    jz .xr
    sub ax, BZ_ACC
.xr:
    test bl, BZ_K_R
    jz .xd
    add ax, BZ_ACC
.xd:
    call bz_drag
    mov [bz_vx], ax
    mov ax, [bz_vy]
    test bl, BZ_K_U
    jz .yd
    sub ax, BZ_ACC
.yd:
    test bl, BZ_K_D
    jz .ydr
    add ax, BZ_ACC
.ydr:
    call bz_drag
    mov [bz_vy], ax
    mov ax, [bz_vx]             ; the move: 24.8 fixed point
    cwd
    add [bz_bx], ax
    adc [bz_bx + 2], dx
    mov ax, [bz_vy]
    cwd
    add [bz_by], ax
    adc [bz_by + 2], dx
    mov bx, bz_bx               ; the edges
    mov ax, BZ_BXMIN
    mov dx, BZ_BXMAX
    call bz_edge
    mov bx, bz_by
    mov ax, BZ_BYMIN
    mov dx, BZ_BYMAX
    call bz_edge
    pop dx
    pop bx
    pop ax
    ret

; BX = bz_bx or bz_by (its velocity is the word at BX + (bz_vx - bz_bx) for x,
; + (bz_vy - bz_by) for y), AX = the least px, DX = the most: clamp, and
; reflect the velocity with a restitution of one half.  Clobbers AX, DX.
bz_edge:
    push si
    mov si, bz_vx
    cmp bx, bz_bx
    je .v
    mov si, bz_vy
.v:
    cmp [bx + 1], ax            ; (the integer px word; < 2048, so signed is fine)
    jl .lo
    cmp [bx + 1], dx
    jl .out
    mov byte [bx], 0            ; at or past the most: exactly on the edge...
    mov [bx + 1], dx
    mov byte [bx + 3], 0
    cmp word [si], 0            ; ...and an outward move bounces
    jle .out
    jmp .refl
.lo:
    mov byte [bx], 0            ; under the least: exactly on the edge...
    mov [bx + 1], ax
    mov byte [bx + 3], 0
    cmp word [si], 0
    jge .out
.refl:
    mov ax, [si]
    neg ax
    sar ax, 1
    mov [si], ax
.out:
    pop si
    ret

; AX = a velocity -> AX after one step's drag (|v|/64 rounded up, toward 0),
; clamped to +-BZ_VMAX.  Preserves all else.
bz_drag:
    push cx
    push dx
    mov dx, ax
    or ax, ax
    jns .p
    neg ax
.p:
    add ax, 63
    mov cl, 6
    shr ax, cl
    or dx, dx
    jns .sub
    add dx, ax
    jmp .clamp
.sub:
    sub dx, ax
.clamp:
    cmp dx, BZ_VMAX
    jle .lo
    mov dx, BZ_VMAX
.lo:
    cmp dx, -BZ_VMAX
    jge .out
    mov dx, -BZ_VMAX
.out:
    mov ax, dx
    pop dx
    pop cx
    ret

; -----------------------------------------------------------------------------
; bz_auto - THE AUTOPILOT (SPEC.md 128.6): the keys it would hold toward the
; next waypoint of bzconst.inc's BZ_WAYTAB (a long diagonal descent, a
; traverse left, the return up - up-right, then up-left to the start - a climb,
; a sprint down).  It wants a velocity of 8/256 px a
; step per px of distance, at most BZ_VMAX, and presses the arrow that closes
; the gap.  Deterministic from the first frame.  Out: BL.  Preserves all else.
; -----------------------------------------------------------------------------
bz_auto:
    push ax
    push cx
    push dx
    push si
.again:
    mov si, [bz_wp]
    shl si, 1
    shl si, 1
    add si, bz_way
    mov ax, [si]
    sub ax, [bz_bx + 1]         ; AX = dx, px
    mov cx, [si + 2]
    sub cx, [bz_by + 1]         ; CX = dy
    cmp word [bz_wp], BZ_NWAY - 1
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

bz_way:
    BZ_WAYTAB

; -----------------------------------------------------------------------------
; bz_camera - the ball's integer position and frame, then the new window.
; Runs ONCE A FRAME, after the frame's steps (SPEC.md 128.9: the camera is part
; of the simulation, and its cadence is the frame rate's).  The first frame
; centres the window on the ball and is a FULL WRITE, as is any step past
; BZ_MAXR/BZ_MAXC.  After it, the MODE (bz_cmode; GLIDE in a benchmark):
;
;   GLIDE   (bz_camglide) rests while the ball is inside the dead zone and the
;           band, and PANS when it leaves them, ahead of the ball, until the
;           target is reached: the camera either rests or moves fast
;   FOLLOW  (bz_camfollow) a camera velocity eased toward the ball's; its
;           position steps the window at an even cadence
;   TRICKLE wave 0's camera, unchanged (SPEC.md 128.5), for the A/B
;
; Every mode keeps the ball's centre inside the dead zone (the window's middle
; half across) and the band (its middle third down) wherever the course lets
; the window go, at most BZ_MAXR rows and BZ_MAXC columns a frame, clamped to
; the course - so 128.2 rule 4's column split is the same in all three.
; Sets bz_px, bz_py, bz_frm, bz_R0n, bz_c0n, bz_dr, bz_dc, bz_full, bz_meas,
; bz_cuse.  Preserves nothing.
; -----------------------------------------------------------------------------
bz_camera:
    mov ax, [bz_bx + 1]
    mov [bz_px], ax
    mov bx, [bz_by + 1]
    mov [bz_py], bx
    and ax, 7                   ; f = (py & 7) * 8 + (px & 7)
    and bx, 7
    shl bx, 1
    shl bx, 1
    shl bx, 1
    add ax, bx
    mov [bz_frm], ax
    mov al, [bz_cmode]          ; the mode this frame: the benchmark's is GLIDE
    cmp byte [bz_mode], 0       ; whatever the player chose, so its route and
    je .muse                    ; its numbers stay comparable (bz_cmode is
    xor al, al                  ; left as it was)
.muse:
    mov [bz_cuse], al
    mov cl, [bz_lsh]
    cmp byte [bz_first], 0
    je .modes
    ; --- the first frame: the window centred on the ball ---
    mov byte [bz_first], 0
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
    jmp .sync
.modes:
    mov al, [bz_cuse]
    cmp al, 1
    jb .glide
    je .follow
    ; --- TRICKLE, wave 0's camera (SPEC.md 128.5) ---
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
    jmp .moved
.glide:
    call bz_camglide
    jmp .moved
.follow:
    call bz_camfollow
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
    jbe .synced
.full:
    mov byte [bz_full], 1
.synced:
    cmp byte [bz_cuse], 1
    je .decided
.sync:
    ; --- every mode but FOLLOW: FOLLOW's camera sits ON the window, at rest,
    ; so choosing it starts from where the picture is; and GLIDE's pans are
    ; off outside GLIDE.  (The ball's last position is kept below.)
    mov cl, [bz_lsh]
    mov ax, [bz_c0n]
    shl ax, 1
    shl ax, 1
    shl ax, 1
    mov [bz_fcx + 1], ax        ; (+ 1, the integer word; +3 is 0 below)
    mov ax, [bz_R0n]
    shl ax, cl
    mov [bz_fcy + 1], ax
    xor ax, ax
    mov [bz_fcx], al
    mov [bz_fcy], al
    mov [bz_fcx + 3], al
    mov [bz_fcy + 3], al
    mov [bz_fvx], ax
    mov [bz_fvy], ax
    cmp byte [bz_cuse], 0
    je .decided
    mov [bz_gpx], ax            ; (bz_gpx and bz_gpy)
.decided:
    mov ax, [bz_bx]             ; FOLLOW's next frame measures the ball's
    mov [bz_lbx], ax            ; travel from here (the low word of 24.8 is
    mov ax, [bz_by]             ; enough: a frame moves it < 128 px)
    mov [bz_lby], ax
    mov ax, [bz_R0n]
    sub ax, [bz_R0]
    mov [bz_dr], ax
    mov ax, [bz_c0n]
    sub ax, [bz_c0]
    mov [bz_dc], ax
    mov al, [bz_full]           ; measured: a benchmark's frames but a full
    xor al, 1                   ; write; PLAY measures nothing, since nothing
    and al, [bz_mode]           ; reads it (bz_mode is 0 or 1)
    mov [bz_meas], al
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
; ball is faster than 4 px a frame (bz_gfx), or while the ball is still
; outside the dead zone (the first frame of a pan, so the edge holds).
;
; DOWN: the same on rows: at rest inside the band [L/3, 2L/3] (the middle
; third of BZ_LINES lines, 66 .. 133), and when the ball leaves it a pan to
; the row that puts it on the band's trailing edge - a sixth of the window
; behind the centre, so the camera leads by a sixth - at one row a frame, two
; while the ball is faster than 2 lines a frame (bz_gfy), and a second one
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
    mov dx, [bz_vx]             ; ...every frame while the ball is fast
    call bz_abs
    cmp dx, [bz_gfx]
    jbe .xdone
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
    mov dx, [bz_vy]             ; two while the ball is fast...
    call bz_abs
    cmp dx, [bz_gfy]
    ja .y2
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

; -----------------------------------------------------------------------------
; bz_camfollow - FOLLOW (SPEC.md 128.9): a camera that MOVES WITH the ball, so
; its steps come at an even cadence matched to the ball's speed.  CL =
; [bz_lsh].  Sets [bz_c0n], [bz_R0n].  Per axis, each frame:
;
;   d   = the ball's travel this frame, 1/256 px (lines): bz_bx - bz_lbx
;   e   = the ball's centre - the camera's centre, px (lines)
;   v  += (d + 8e - v) / 4        the camera velocity, 1/256 px a frame: it
;                                 eases toward the ball's by a QUARTER of the
;                                 difference a frame, with a correction of
;                                 e/32 px a frame toward the window's centre
;   pos += v                      24.8, clamped to the course (v = 0 there)
;
; and the window steps a column (row) when pos is a whole column (row) or
; more away from it - when pos CROSSES the next one, so a camera moving at a
; steady speed steps every 8 px (rl lines) of it.  Then the dead zone and the
; band are held as edges (a step more if the ball is still outside, within
; BZ_MAXC / BZ_MAXR), and pos is put back on the window if it drifted a whole
; step from it (an edge or the course moved the window, not pos).
;
; The constants: the ease of 1/4 smooths the ball's frame-to-frame travel
; (0, 1 or 2 steps a frame) into a speed; the correction's 1/32 a frame is a
; time constant of about 28 frames with the ease (both roots of the loop
; real, 0.965 and 0.777: it settles without overshoot), slow enough that the
; cadence is the ball's, not the correction's.  (Asked for by feel: the owner
; chooses between the modes; these are the first guess.)
; -----------------------------------------------------------------------------
bz_camfollow:
    ; ---- across ----
    mov ax, [bz_bx]
    sub ax, [bz_lbx]            ; AX = d
    mov bx, [bz_px]
    add bx, 8
    mov dx, [bz_W]
    shl dx, 1
    shl dx, 1                   ; 4W: half the window's px
    add dx, [bz_fcx + 1]
    sub bx, dx                  ; BX = e
    shl bx, 1
    shl bx, 1
    shl bx, 1
    add ax, bx                  ; the velocity wanted
    sub ax, [bz_fvx]
    sar ax, 1
    sar ax, 1
    add ax, [bz_fvx]
    mov [bz_fvx], ax
    cwd
    add [bz_fcx], ax
    adc [bz_fcx + 2], dx
    test byte [bz_fcx + 3], 80h ; the course: px 0 .. cmax*8
    jz .xnn
    xor ax, ax
    mov [bz_fcx], ax
    mov [bz_fcx + 2], ax
    mov [bz_fvx], ax
    jmp .xpos
.xnn:
    mov ax, [bz_cmax]
    shl ax, 1
    shl ax, 1
    shl ax, 1
    cmp [bz_fcx + 1], ax
    jbe .xpos
    mov [bz_fcx + 1], ax
    mov byte [bz_fcx], 0
    mov word [bz_fvx], 0
.xpos:
    mov si, [bz_c0]             ; the step: pos a whole column away
    mov bx, si
    shl bx, 1
    shl bx, 1
    shl bx, 1
    mov ax, [bz_fcx + 1]
    sub ax, bx
    cmp ax, 8
    jl .xnr
    inc si
    jmp .xedge
.xnr:
    cmp ax, -8
    jg .xedge
    dec si
.xedge:
    mov ax, [bz_px]             ; the dead zone's edges
    add ax, 8
    mov bx, si
    shl bx, 1
    shl bx, 1
    shl bx, 1
    sub ax, bx
    mov dx, [bz_W]
    shl dx, 1
    cmp ax, dx
    jge .xe2
    mov si, [bz_c0]
    dec si
    jmp .xcl
.xe2:
    mov bx, dx
    shl bx, 1
    add bx, dx
    cmp ax, bx
    jle .xcl
    mov si, [bz_c0]
    inc si
.xcl:
    or si, si
    jge .xcl2
    xor si, si
.xcl2:
    cmp si, [bz_cmax]
    jle .xcl3
    mov si, [bz_cmax]
.xcl3:
    mov [bz_c0n], si
    shl si, 1                   ; pos back on the window if a step away
    shl si, 1
    shl si, 1
    mov ax, [bz_fcx + 1]
    sub ax, si
    cmp ax, 8
    jge .xsnap
    cmp ax, -8
    jg .down
.xsnap:
    mov [bz_fcx + 1], si
    mov byte [bz_fcx], 0
.down:
    ; ---- down ----
    mov ax, [bz_by]
    sub ax, [bz_lby]            ; AX = d
    mov bx, [bz_py]
    add bx, 8
    mov dx, [bz_fcy + 1]
    add dx, BZ_LINES / 2
    sub bx, dx                  ; BX = e
    shl bx, 1
    shl bx, 1
    shl bx, 1
    add ax, bx
    sub ax, [bz_fvy]
    sar ax, 1
    sar ax, 1
    add ax, [bz_fvy]
    mov [bz_fvy], ax
    cwd
    add [bz_fcy], ax
    adc [bz_fcy + 2], dx
    test byte [bz_fcy + 3], 80h ; the course: lines 0 .. rmax << lsh
    jz .ynn
    xor ax, ax
    mov [bz_fcy], ax
    mov [bz_fcy + 2], ax
    mov [bz_fvy], ax
    jmp .ypos
.ynn:
    mov ax, [bz_rmax]
    shl ax, cl
    cmp [bz_fcy + 1], ax
    jbe .ypos
    mov [bz_fcy + 1], ax
    mov byte [bz_fcy], 0
    mov word [bz_fvy], 0
.ypos:
    mov si, [bz_R0]             ; the steps: pos a whole row away, twice
    mov ch, BZ_MAXR
.ystep:
    mov bx, si
    shl bx, cl
    mov ax, [bz_fcy + 1]
    sub ax, bx
    cmp ax, [bz_rl]
    jl .ynd
    inc si
    jmp .ynx
.ynd:
    mov dx, [bz_rl]
    neg dx
    cmp ax, dx
    jg .ynx
    dec si
.ynx:
    dec ch
    jnz .ystep
    mov ch, BZ_MAXR             ; the band's edges, within BZ_MAXR of R0
.yedge:
    mov ax, [bz_py]
    add ax, 8
    mov bx, si
    shl bx, cl
    sub ax, bx
    mov dx, [bz_R0]
    cmp ax, BZ_LINES / 3
    jge .ye2
    sub dx, BZ_MAXR
    cmp si, dx
    jle .ycl
    dec si
    jmp .yen
.ye2:
    cmp ax, 2 * BZ_LINES / 3
    jle .ycl
    add dx, BZ_MAXR
    cmp si, dx
    jge .ycl
    inc si
.yen:
    dec ch
    jnz .yedge
.ycl:
    or si, si
    jge .ycl2
    xor si, si
.ycl2:
    cmp si, [bz_rmax]
    jle .ycl3
    mov si, [bz_rmax]
.ycl3:
    mov [bz_R0n], si
    shl si, cl                  ; pos back on the window if a row away
    mov ax, [bz_fcy + 1]
    sub ax, si
    cmp ax, [bz_rl]
    jge .ysnap
    mov dx, [bz_rl]
    neg dx
    cmp ax, dx
    jg .out
.ysnap:
    mov [bz_fcy + 1], si
    mov byte [bz_fcy], 0
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
; bz_mkboxes - the frame's boxes (SPEC.md 128.4): the new footprint (the ball's
; 5 bytes x 16 lines, in words), and with it the old one - as ONE box, their
; union, when that fits BZ_BOXW x BZ_BOXH, else as two.  Two boxes may
; overlap; both are composed from the course and the ball, and the SECOND
; skips the overlap when it is written (bz_boxw, the band set here: SPEC.md
; 128.9 item 5).  A full write needs only the new one.  Each box is clipped to
; the NEW window; what the old footprint loses to the clip needs no restoring
; (SPEC.md 128.4).  AN IDLE BALL - the same position as last frame, so the
; same frame, and no scroll - needs NO box: the card already holds it (item
; 5).  Preserves nothing.
; -----------------------------------------------------------------------------
bz_mkboxes:
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
    mov word [bz_xhi], 0        ; no overlap band
    mov ax, [bz_px]
    mov bx, ax
    mov cl, 3
    shr ax, cl
    mov [bz_nfx0], ax
    shr bx, 1
    shr bx, 1
    add bx, BZ_BAL_RB - 1
    shr bx, 1
    mov [bz_nfx1], bx
    mov ax, [bz_py]
    mov [bz_nfy0], ax
    add ax, BZ_BAL_ROWS - 1
    mov [bz_nfy1], ax
    mov word [bz_nbox], 0
    cmp byte [bz_full], 0
    jne .new
    cmp byte [bz_oldv], 0
    je .new
    or bp, bp
    jnz .union
    ret                         ; idle: nothing to compose or write
.union:
    mov ax, [bz_ofx0]           ; the union
    cmp ax, [bz_nfx0]
    jle .ux0
    mov ax, [bz_nfx0]
.ux0:
    mov bx, [bz_ofx1]
    cmp bx, [bz_nfx1]
    jge .ux1
    mov bx, [bz_nfx1]
.ux1:
    mov cx, [bz_ofy0]
    cmp cx, [bz_nfy0]
    jle .uy0
    mov cx, [bz_nfy0]
.uy0:
    mov dx, [bz_ofy1]
    cmp dx, [bz_nfy1]
    jge .uy1
    mov dx, [bz_nfy1]
.uy1:
    mov si, bx
    sub si, ax
    cmp si, BZ_BOXW - 1
    ja .two
    mov si, dx
    sub si, cx
    cmp si, BZ_BOXH - 1
    ja .two
    jmp bz_addbox               ; one box, and the frame's boxes are made
.two:
    mov ax, [bz_ofx0]
    mov bx, [bz_ofx1]
    mov cx, [bz_ofy0]
    mov dx, [bz_ofy1]
    call bz_addbox
    call .new
    cmp word [bz_nbox], 2
    jne .out
    ; the overlap of the two clipped boxes, in the second box's terms: its
    ; words [xa, xb) on its lines whose lines-left count is in (xlo, xhi]
    mov si, bz_boxes
    mov ax, [si]                ; x: [max(x0, x0'), min(x0 + w, x0' + w'))
    mov bx, [si + BZ_BOXD]
    cmp ax, bx
    jge .xl
    mov ax, bx
.xl:
    mov cx, [si]
    add cx, [si + 4]
    mov dx, bx
    add dx, [si + BZ_BOXD + 4]
    cmp cx, dx
    jle .xr
    mov cx, dx
.xr:
    cmp ax, cx
    jge .out                    ; apart in x
    sub ax, bx
    sub cx, bx
    mov [bz_xa], ax
    mov [bz_xb], cx
    mov ax, [si + 2]            ; y: [max(y0, y0'), min(y0 + h, y0' + h'))
    mov bx, [si + BZ_BOXD + 2]
    cmp ax, bx
    jge .yt
    mov ax, bx
.yt:
    mov cx, [si + 2]
    add cx, [si + 6]
    mov dx, bx
    add dx, [si + BZ_BOXD + 6]  ; DX = y0' + h', the second box's end
    cmp cx, dx
    jle .yb
    mov cx, dx
.yb:
    cmp ax, cx
    jge .out                    ; apart in y
    sub dx, ax
    mov [bz_xhi], dx            ; the band's first line has xhi lines left...
    add dx, ax
    sub dx, cx
    mov [bz_xlo], dx            ; ...and the line after its last, xlo
.out:
    ret
.new:
    mov ax, [bz_nfx0]
    mov bx, [bz_nfx1]
    mov cx, [bz_nfy0]
    mov dx, [bz_nfy1]
    jmp bz_addbox

; AX = x0, BX = x1 (words), CX = y0, DX = y1 (lines), inclusive: clipped to
; the new window and, if anything is left, appended to bz_boxes.  Clobbers
; AX-DX, SI, DI (never BP).
%if BZ_BOXD != 10
 %error "bz_addbox scales the box index by 10 = BZ_BOXD"
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
    push cx
    mov si, [bz_R0n]
    mov cl, [bz_lsh]
    shl si, cl                  ; the window's top line
    pop cx
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
    mov si, [bz_nbox]           ; 0 or 1: a frame has at most two boxes
    mov di, si
    shl si, 1
    shl si, 1
    add si, di
    shl si, 1                   ; x BZ_BOXD (10)
    add si, bz_boxes
    neg di                      ; the buffer: box 0's, or box 1's BZ_BOXB on
    and di, BZ_BOXB
    add di, bz_boxbuf
    mov [si], ax
    mov [si + 2], cx
    inc bx
    mov [si + 4], bx
    inc dx
    mov [si + 6], dx
    mov [si + 8], di
    inc word [bz_nbox]
.out:
    ret

; -----------------------------------------------------------------------------
; bz_csplit - where this frame's entering column [bz_ccol] splits round the
; boxes (SPEC.md 128.2 rule 3 and 4): CX = the window rows of the column that
; go BEFORE the boxes, the rest going after them.  The column is written from
; the retrace and outruns the beam (~0.4k clocks a CGA row against 0.6k), but a
; whole column first would leave the box to start some 20-30k clocks after the
; retrace, with the beam already in the middle third where the camera keeps
; the ball, and the box writer is slower than the beam: the ball would show
; half old, half new for a refresh.  So: the column down to the row above the
; boxes' top, then the boxes, then the rest of the column - which is behind
; the box's rows on the glass and gains on the beam again.  A box that holds a
; cell of the column must follow ALL of it (the column would write the course
; over the ball), so then CX = H, the whole column first; with no box, too.
; In steady state no box touches the column: the dead zone keeps the ball two
; words or more from either edge while the camera steps sideways.
; Clobbers AX, BX, DX, SI.
; -----------------------------------------------------------------------------
bz_csplit:
    mov cx, [bz_H]
    mov dx, [bz_R0n]
    push cx
    mov cl, [bz_lsh]
    shl dx, cl                  ; DX = the window's top line
    pop cx
    mov word [bz_cbot], 0
    mov si, bz_boxes
    mov bx, [bz_nbox]
    or bx, bx
    jz .out
.box:
    mov ax, [bz_ccol]           ; the column inside [x0, x0 + w): the whole
    sub ax, [si]                ; column first (unsigned: left of x0 is huge)
    cmp ax, [si + 4]
    jb .whole
    mov ax, [si + 2]            ; the boxes' lowest line in the window (the
    add ax, [si + 6]            ; row-0 case's beam, bz_latechk)
    dec ax
    sub ax, dx
    cmp ax, [bz_cbot]
    jbe .low
    mov [bz_cbot], ax
.low:
    mov ax, [si + 2]            ; the box's top row in the window
    sub ax, dx
    push cx
    mov cl, [bz_lsh]
    shr ax, cl
    pop cx
    cmp ax, cx
    jae .next
    mov cx, ax
.next:
    add si, BZ_BOXD
    dec bx
    jnz .box
    jcxz .row0
.out:
    ret
.whole:
    mov cx, [bz_H]
    ret
.row0:                          ; a box at window row 0 (SPEC.md 128.9 item 6):
    mov cx, [bz_cbot]           ; no column rows above it, so the column's rows
    mov dx, cx                  ; down to the boxes' LAST line go first instead
    mov cl, [bz_lsh]            ; - they outrun the beam, the box does not -
    shr dx, cl                  ; and bz_tb times the box (bz_row0)
    inc dx
    mov cx, dx
    mov byte [bz_row0], 1
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
