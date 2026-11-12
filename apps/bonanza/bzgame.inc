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
;   bz_res      byte   1 = the bz_r* copy below holds a finished benchmark
;   bz_rframes, bz_rmfr, bz_rncol, bz_rnrow, bz_rnfull, bz_rmiss, bz_rfmax,
;                      bz_racc: that copy, the same layout as bz_frames ..
;                      bz_acc
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
; beam (SPEC.md 128.2 rule 4 as amended by the wave-0 fix stage).
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
BZ_K_L      equ 1               ; bz_keys: the arrows held
BZ_K_R      equ 2
BZ_K_U      equ 4
BZ_K_D      equ 8
BZ_LIVE     equ 40              ; bytes of bz_frames .. bz_acc (the results copy)

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
VAR bz_pad0,1
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
VAR bz_rframes,2
VAR bz_rmfr,2
VAR bz_rncol,2
VAR bz_rnrow,2
VAR bz_rnfull,2
VAR bz_rmiss,2
VAR bz_rfmax,4
VAR bz_racc,4 * BZ_NPART
VAR bz_tos,2
; the clock
VAR bz_subs,2
VAR bz_pitl,2
VAR bz_msubs,2
VAR bz_mpit,2
VAR bz_lsubs,2
VAR bz_fper,4
VAR bz_mlim,2
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
VAR bz_bw,2
VAR bz_bx2,2
VAR bz_imin,2
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
; frame is measured, and the mark becomes the base.  A mark costs ~0.5k clocks
; of its own (a PIT latch and the sums), billed to the part it closes: the
; small parts' means read that much high.  Preserves all but the flags.
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
    mov ax, [bz_R0n]            ; S = (W*R0 + c0) mod 4096
    mul word [bz_W]
    add ax, [bz_c0n]
    and ax, 0fffh
    call bz_flip
    mov [bz_S], ax
    mov ax, [bz_R0n]
    mov [bz_R0], ax
    mov ax, [bz_c0n]
    mov [bz_c0], ax
    mov word [bz_crest], 0      ; no column rows left for after the boxes
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
    mov bx, 5 * 4               ; (the part the next mark closes: the box write)
    mov si, bz_boxes
    mov cx, [bz_nbox]
    jcxz .wrote
.write:
    call bz_boxw
    add si, BZ_BOXD
    loop .write
.wrote:
    cmp word [bz_crest], 0
    je bz_presented
bz_tc:
    call bz_mark                ; BX = 5*4: the box write ends here
    mov ax, [bz_ccol]           ; the column's rows under the boxes' top row
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

; the arrows held -> [bz_keys].  Preserves all but the flags.
bz_input:
    push ax
    push bx
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
; bz_camera - the ball's integer position and frame, then the new window
; (SPEC.md 128.5): the ball kept inside a vertical BAND of the middle third,
; at most BZ_MAXR rows a frame, and a horizontal DEAD ZONE of the middle half,
; at most BZ_MAXC columns, clamped to the course.  The first frame centres the
; window on the ball and is a FULL WRITE, as is any step past BZ_MAXR/BZ_MAXC.
; Sets bz_px, bz_py, bz_frm, bz_R0n, bz_c0n, bz_dr, bz_dc, bz_full, bz_meas.
; Preserves nothing.
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
    mov cl, [bz_lsh]
    cmp byte [bz_first], 0
    je .follow
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
    jmp .decided
.follow:
    ; --- vertical: the band [T + 1/3, T + 2/3] of the window's lines ---
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
    ; --- horizontal: the dead zone [left + W*2, left + W*6] px ---
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
    xor al, 1                   ; write; PLAY measures nothing, since nothing
    and al, [bz_mode]           ; reads it (bz_mode is 0 or 1)
    mov [bz_meas], al
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
; union, when that fits BZ_BOXW x BZ_BOXH, else as two (which may overlap: both
; are composed from the course and the ball, so an overlap is written twice
; with the same bytes).  A full write needs only the new one.  Each box is
; clipped to the NEW window; what the old footprint loses to the clip needs no
; restoring (SPEC.md 128.4).  Preserves nothing.
; -----------------------------------------------------------------------------
bz_mkboxes:
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
    mov si, bz_boxes
    mov bx, [bz_nbox]
    or bx, bx
    jz .out
.box:
    mov ax, [bz_ccol]           ; the column inside [x0, x0 + w): the whole
    sub ax, [si]                ; column first (unsigned: left of x0 is huge)
    cmp ax, [si + 4]
    jb .whole
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
.out:
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
