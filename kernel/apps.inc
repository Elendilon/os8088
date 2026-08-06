; =============================================================================
; os8088 - apps.inc
;
; The built-in application KINDS (SPEC.md 14): About dialog, Note Pad, Timer
; and Bounce. Nothing is created at boot - instances are launched on demand
; by app_launch (SPEC.md 29), which allocates a state block from the kind's
; pool, creates the window from the kind's template, and spawns the kind's
; task (Timer/Bounce run one task per instance). Closing an instance frees
; all of it: the UI task sets the die flag (I_STATE=2) and hides the window;
; the task notices at its next wake and tears down via inst_task_die.
;
; Paint procs and key handlers run with the gfx lock already held by the
; caller (SPEC.md 11), find their instance state via inst_of_win + I_SPTR,
; and never lock, block or spawn; the Timer/Bounce tasks take the lock
; themselves and arm a clip region under it (SPEC.md 11.3) before touching
; the screen. Background tasks use only os8088 primitives and [ticks] - no
; BIOS calls (SPEC.md 7).
;
; app_bounce_task below is the REFERENCE IMPLEMENTATION for a package's
; worker task (SPEC.md 20.6): sleep, take the lock, wm_clip_set under it,
; draw briefly, release, check the die flag. Keep its shape - the author
; rules point at it.
; =============================================================================

; --- geometry ----------------------------------------------------------------
APP_BALL_XMAX   equ 150 - 2 - 8             ; bounce content w=148, 8px square
APP_BALL_YMAX   equ 130 - TITLE_H - 1 - 8   ; bounce content rows are
                                            ; y+TITLE_H..y+h-2 inclusive = 111

; Timer (SPEC.md 14): "HH:MM:SS" over a row of three buttons. The window is
; fixed-size and never resizable, and 160x60 is inside every adapter's
; desktop band (CGA's is the tightest at 640x157), so wm_fit cannot shrink it
; and the content box is APP_TMR_CW x 41 on all three - which is what lets
; these be constants rather than another read of [vid_*] (SPEC.md 1/39.7).
APP_TMR_W    equ 160                        ; frame width / height
APP_TMR_H    equ 60
APP_TMR_CW   equ APP_TMR_W - 2              ; content width = 158
APP_TMR_DY   equ 5                          ; digits: top, content-relative
APP_TMR_DW   equ 8 * 8                      ; ...and their 8-cell width
APP_TMR_NB   equ 3                          ; buttons: count, size and pitch
APP_TMR_BW   equ 46
APP_TMR_BH   equ 15
APP_TMR_BGAP equ 6
APP_TMR_BY   equ 20                         ; ...top, content-relative: rows
                                            ; 20..34 of the 41 the content has
APP_TMR_BX   equ (APP_TMR_CW - APP_TMR_NB * APP_TMR_BW \
                  - (APP_TMR_NB - 1) * APP_TMR_BGAP) / 2   ; = 4, the left inset
APP_TMR_LT   equ (APP_TMR_BH - 8) / 2       ; a label's top within its button

APP_TMR_START equ 0             ; button indices - the order they are drawn,
APP_TMR_STOP  equ 1             ; hit-tested and dispatched in
APP_TMR_RESET equ 2

; --- per-instance state layouts (pool strides pinned in SPEC.md 29.3) --------
TMR_HRS   equ 0                 ; byte
TMR_MIN   equ 1                 ; byte
TMR_SEC   equ 2                 ; byte
TMR_RUN   equ 3                 ; byte: 0 stopped, 1 running (the old padding
                                ; byte, so the stride is still 8)
TMR_LAST  equ 4                 ; word: last [ticks] sample
TMR_ACC   equ 6                 ; word: tenth-of-tick accumulator; stride 8

BAL_X     equ 0                 ; words: content-relative pos + velocity
BAL_Y     equ 2
BAL_VX    equ 4
BAL_VY    equ 6                 ; stride 8

; --- window templates: {x, y, w, h, title, paint, onkey, onclick} words ------
; The Timer's x keeps its whole cap-10 cascade (+16 per pool slot, SPEC.md
; 29.4) on a 640px screen: 330 + 144 + 160 = 634.
app_tpl_about:  dw 170, 140, 300, 120, app_ttl_about,  app_about_paint,  0, 0
app_tpl_timer:  dw 330,  60, APP_TMR_W, APP_TMR_H, app_ttl_timer, app_tmr_paint
                dw 0, app_tmr_onclick
app_tpl_bounce: dw 300, 150, 150, 130, app_ttl_bounce, app_bounce_paint, 0, 0

app_ttl_about:  db 'About os8088', 0
app_ttl_timer:  db 'Timer', 0
app_ttl_bounce: db 'Bounce', 0

app_tmr_s_start: db 'Start', 0
app_tmr_s_stop:  db 'Stop', 0
app_tmr_s_reset: db 'Reset', 0
app_tmr_lbl:     dw app_tmr_s_start, app_tmr_s_stop, app_tmr_s_reset

app_about_s1:   db 'os8088 1.0', 0
app_about_s2:   db 'a graphical OS for the 8086', 0
; third line, one word per scheduler mode (SPEC.md 8.2/14)
app_about_s3p:  db 'pre-emptive', 0
app_about_s3c:  db 'cooperative', 0
; fourth line: the screen this machine actually got (SPEC.md 39). Indexed by
; [vid_kind], so it can never disagree with what is on the glass - the old
; third line asserted '640x480 - 16 colors' unconditionally, which stopped
; being true the moment the kernel learned to drive a mono card.
app_about_vid:  dw app_about_v0, app_about_v1, app_about_v2
app_about_v0:   db 'VGA - 640x480 - 16 colors', 0
app_about_v1:   db 'Hercules - 720x348 - mono', 0
app_about_v2:   db 'CGA - 640x200 - mono', 0

; =============================================================================
; Kind init procs (KD_INIT contract, SPEC.md 29.3): in BX = window ptr,
; DI = state block ptr, SI = instance record ptr; preserve all registers;
; run on the UI task with no lock held, window not yet visible.
; =============================================================================

; ---- app_tmr_kinit - fresh Timer: 00:00:00, seeded now, and RUNNING ---------
; Opening the Timer starts it (SPEC.md 14) - the buttons are there to stop it
; and to put it back, not to arm it.
app_tmr_kinit:
    push ax
    mov byte [ss:di+TMR_HRS], 0
    mov byte [ss:di+TMR_MIN], 0
    mov byte [ss:di+TMR_SEC], 0
    mov byte [ss:di+TMR_RUN], 1
    mov ax, [ticks]
    mov [ss:di+TMR_LAST], ax
    mov word [ss:di+TMR_ACC], 0
    pop ax
    ret

; ---- app_bounce_kinit - fresh Bounce: ball at (4,4), velocity (3,2) ----------
app_bounce_kinit:
    mov word [ss:di+BAL_X], 4
    mov word [ss:di+BAL_Y], 4
    mov word [ss:di+BAL_VX], 3
    mov word [ss:di+BAL_VY], 2
    ret

; =============================================================================
; About
; =============================================================================

; -----------------------------------------------------------------------------
; app_about_paint - W_PAINT for the About window (stateless)
; in:  SI = window ptr (content already white-filled, gfx lock held)
; out: nothing
; clobbers: nothing (flags only)
; Four black lines, each centered in the content. The third line's
; scheduling word tracks the live mode (sched_mode_get) and the fourth names
; the video adapter the boot probe found (SPEC.md 39.1). app_about_center
; re-measures every string, so unequal lengths are fine.
; -----------------------------------------------------------------------------
app_about_paint:
    push ax
    push bx
    push cx
    push dx
    push si

    mov byte [gfx_color], CBLACK
    mov bx, si                  ; window ptr for the centering helper
    mov dx, [bx+W_Y]
    add dx, TITLE_H + 22        ; first line: content top + 22 (four lines of
                                ; 8px on 16px pitch, centred in 101px)
    mov si, app_about_s1
    call app_about_center
    add dx, 16
    mov si, app_about_s2
    call app_about_center
    add dx, 16
    mov si, app_about_s3p       ; third line follows the live scheduler mode
    call sched_mode_get         ; AL = 0 pre-emptive, 1 cooperative
    or al, al
    jz .s3
    mov si, app_about_s3c
.s3:
    call app_about_center
    add dx, 16
    push bx                     ; fourth line: the adapter in use. BX is the
    mov bl, [vid_kind]          ; window ptr app_about_center wants, so it
    xor bh, bh                  ; only borrows it as the table index
    shl bx, 1
    mov si, [bx + app_about_vid]
    pop bx
    call app_about_center

    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; app_about_center - draw one string centered horizontally in a window
; in:  SI = NUL string, BX = window ptr, DX = y
; out: nothing
; clobbers: AX, CX (internal helper)
; -----------------------------------------------------------------------------
app_about_center:
    call font_width             ; AX = string width, px
    mov cx, [bx+W_W]
    sub cx, 2                   ; content width
    sub cx, ax
    shr cx, 1                   ; centering offset
    add cx, [bx+W_X]
    inc cx                      ; content left = W_X + 1
    call font_str
    ret

; =============================================================================
; Timer
; =============================================================================

; -----------------------------------------------------------------------------
; app_tmr_task - per-instance task: keep time, redraw HH:MM:SS twice a
;                second, die on request
; in:  DX = instance index (the spawn argument, SPEC.md 8); never returns
; The accumulator design is binding (SPEC.md 14): delta ticks since the last
; sample (wrap-safe subtraction) are added to TMR_ACC in tenths of a tick;
; every 182 tenths (18.2 ticks) advances one second with carries. The tick is
; SAMPLED every iteration whether the timer runs or not - a stopped interval
; is discarded rather than banked, which is the whole of what Stop means -
; and only a running timer accumulates it. Only the drawing is conditional,
; on the window being visible and on wm_clip_set finding any of it uncovered,
; both under the gfx lock (SPEC.md 11.3). A half-covered Timer redraws the
; half you can see instead of freezing. I_STATE = 2 at wake = close
; requested: tear down via inst_task_die (SPEC.md 29).
;
; The task draws the DIGITS and nothing else. The three buttons change only
; when they are clicked, so they are drawn by W_PAINT and by the click path,
; both of which run unclipped - see app_tmr_btn.
; -----------------------------------------------------------------------------
app_tmr_task:
    mov al, dl
    call inst_ptr               ; DI = our instance record
    mov bp, di                  ; BP = record for life
    mov si, [ds:bp+I_SPTR]      ; SI = time state for life (BP addresses
                                ; SS by default - SPEC.md 1 rule 3)
.loop:
    mov ax, 9
    call task_sleep
    cmp byte [ds:bp+I_STATE], 2    ; close requested?
    je .die

    ; --- time-keeping, every iteration ---
    mov ax, [ticks]
    mov dx, ax
    sub ax, [ss:si+TMR_LAST]       ; delta, safe across the 65536 wrap
    mov [ss:si+TMR_LAST], dx       ; sampled even while stopped, so a stop
                                   ; costs its interval instead of banking it
    cmp byte [ss:si+TMR_RUN], 0
    je .draw                       ; stopped: the delta goes nowhere
    mov dx, 10
    mul dx                      ; DX:AX = delta * 10 (tenths of a tick) - keep
    add ax, [ss:si+TMR_ACC]        ; the high half: one long gfx_lock starvation
    adc dx, 0                   ; (a held-open menu) can owe > 65535 tenths
    mov cx, 182
    div cx                      ; AX = whole seconds owed, DX = leftover
    mov [ss:si+TMR_ACC], dx        ; (quotient <= 3602, so DIV cannot fault)
    mov cx, ax
.adv:
    jcxz .draw
    dec cx
    mov al, [ss:si+TMR_SEC]        ; + 1 second, with carries
    inc al
    mov [ss:si+TMR_SEC], al
    cmp al, 60
    jb .adv
    mov byte [ss:si+TMR_SEC], 0
    mov al, [ss:si+TMR_MIN]
    inc al
    mov [ss:si+TMR_MIN], al
    cmp al, 60
    jb .adv
    mov byte [ss:si+TMR_MIN], 0
    mov al, [ss:si+TMR_HRS]
    inc al
    mov [ss:si+TMR_HRS], al
    cmp al, 24
    jb .adv
    mov byte [ss:si+TMR_HRS], 0
    jmp .adv

    ; --- drawing, only when the window can actually be seen ---
.draw:
    call gfx_lock
    mov bx, [ds:bp+I_WIN]
    test word [bx+W_FLAGS], 2   ; re-check under the lock (SPEC.md 14)
    jz .skip
    call wm_clip_set            ; CF = 1: not one visible pixel (SPEC 11.3)
    jc .skip
    mov di, si                  ; DI = time state for the renderer
    call app_tmr_digits         ; black HH:MM:SS on white - the background is
                                ; erased per glyph cell in there, NOT as one
                                ; 64x8 rect (SPEC.md 11.3)
.skip:
    call gfx_unlock
    jmp .loop

.die:
    mov di, bp
    jmp inst_task_die           ; destroys the window, frees the record,
                                ; task_exit - never returns

; -----------------------------------------------------------------------------
; app_tmr_paint - W_PAINT for a Timer window
; in:  SI = window ptr (content already white-filled, gfx lock held)
; out: nothing
; clobbers: nothing (flags only)
; -----------------------------------------------------------------------------
app_tmr_paint:
    push ax
    push bx
    push cx
    push dx
    push si
    push di

    mov bx, si                  ; instance state via the owner table
    call inst_of_win
    jc .done
    mov di, [di+I_SPTR]         ; DI = time state
    call app_tmr_digits         ; digits FIRST: a button may leave the pen
    call app_tmr_btns           ; disabled, and app_tmr_cell's own gfx_pen_live
                                ; is what makes the order not matter

.done:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; app_tmr_onclick - W_ONCLICK for a Timer window (SPEC.md 13/14)
; in:  CX = x, DX = y (screen), SI = window ptr; gfx lock held, and this
;      window is the frontmost one by contract
; out: nothing
; clobbers: nothing (flags only)
;
; Fires on the front window alone, and the clip region is disarmed for the
; whole of a W_ONCLICK dispatch, so what is on screen inside the content is
; exactly what the last paint put there and the redraws below may fill and
; letter freely (the SPEC.md 22.2 argument, one module over).
; -----------------------------------------------------------------------------
app_tmr_onclick:
    push ax
    push bx
    push cx
    push dx
    push si
    push di

    mov bx, si                  ; instance state via the owner table
    call inst_of_win
    jc .done
    mov di, [di+I_SPTR]         ; DI = time state
    call app_tmr_hit            ; AL = button index, CF = 1: not on one
    jc .done
    call app_tmr_bok            ; a greyed control explains itself, so a
    jc .done                    ; refused click says nothing more (SPEC.md 47
                                ; rule 6) - no beep, no notice
    cmp al, APP_TMR_START
    je .start
    cmp al, APP_TMR_STOP
    je .stop

    mov byte [ss:di+TMR_HRS], 0 ; --- Reset: back to 00:00:00, running or not
    mov byte [ss:di+TMR_MIN], 0
    mov byte [ss:di+TMR_SEC], 0
    mov word [ss:di+TMR_ACC], 0 ; the part-second in flight goes too, at both
    mov ax, [ticks]             ; ends of the accumulator
    mov [ss:di+TMR_LAST], ax
    call app_tmr_digits         ; only the digits moved; both pens stand
    jmp short .done

.start:
    mov ax, [ticks]             ; the stopped interval is discarded here as
    mov [ss:di+TMR_LAST], ax    ; well as in the task: up to 9 ticks of it can
    mov byte [ss:di+TMR_RUN], 1 ; be sitting unsampled at the moment of a click
    jmp short .pens
.stop:
    mov byte [ss:di+TMR_RUN], 0
.pens:
    mov al, APP_TMR_START       ; Start and Stop just traded pens; Reset did
    call app_tmr_btn            ; not move, and the digits did not either
    mov al, APP_TMR_STOP
    call app_tmr_btn

.done:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; app_tmr_bok - would this button do anything? (SPEC.md 47 rule 2: the ONE
;               predicate, shared by the greying and the click refusal)
; in:  AL = button index, DI = time state ptr
; out: CF = 0 live, CF = 1 refused
; clobbers: flags (internal helper)
; -----------------------------------------------------------------------------
app_tmr_bok:
    cmp al, APP_TMR_RESET
    je .live                    ; Reset always means something
    cmp byte [ss:di+TMR_RUN], 0
    jne .running
    cmp al, APP_TMR_STOP        ; stopped: there is nothing to stop
    je .no
    jmp short .live
.running:
    cmp al, APP_TMR_START       ; running: there is nothing to start
    je .no
.live:
    clc
    ret
.no:
    stc
    ret

; -----------------------------------------------------------------------------
; app_tmr_btns - draw all three buttons
; in:  BX = window ptr, DI = time state ptr (gfx lock held)
; out: nothing
; clobbers: flags (internal helper)
; -----------------------------------------------------------------------------
app_tmr_btns:
    push ax
    mov al, APP_TMR_START
.next:
    call app_tmr_btn
    inc al
    cmp al, APP_TMR_NB
    jb .next
    pop ax
    ret

; -----------------------------------------------------------------------------
; app_tmr_btn - draw ONE button: erase, frame, centred label, all in the pen
;               its own predicate asks for
; in:  AL = button index, BX = window ptr, DI = time state ptr (lock held)
; out: nothing
; clobbers: flags
;
; The erase is unconditional because a redraw after a click lands on the
; previous pen's frame, and the fill and the label are gated TOGETHER on
; wm_clip_test over the whole button (SPEC.md 11.3's granularity rule): a
; button is one control, so it is drawn whole or not at all, and a fill that
; clips per pixel can never leave a cut row the glyphs then refuse to letter.
; Both callers - W_PAINT and W_ONCLICK - run with the clip disarmed, where
; that test answers "free"; the gate is here so the routine stays safe to
; call from anywhere.
; -----------------------------------------------------------------------------
app_tmr_btn:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp

    xor ah, ah
    mov bp, ax                  ; BP = the index for the whole routine, and a
                                ; VALUE rather than an address (SS is not DS,
                                ; SPEC.md 1 rule 3) - AX, BX, CX and DX are
                                ; all about to be rect corners
    call app_tmr_brect          ; AX,BX,CX,DX = its inclusive screen rect
    call wm_clip_test
    jc .out

    mov byte [gfx_color], CWHITE
    call gfx_fill               ; ...which preserves the rect

    push ax                     ; x1 and y1: the pen wants AL for the index
    push bx
    mov ax, bp
    call app_tmr_bok            ; SPEC.md 47 rule 1: colour and [gfx_dis] set
    call gfx_pen_cf             ; together; rule 2: the same predicate the
    pop bx                      ; click path refuses on
    pop ax
    call gfx_frame              ; the frame greys WITH the label (rule 2),
                                ; never just the caption

    mov si, bp                  ; the label, centred in the button
    shl si, 1
    mov si, [si + app_tmr_lbl]
    mov bp, ax                  ; BP = x1, DI = y1 - the index has done its
    mov di, bx                  ; work, and so has the state ptr in DI
    call font_width             ; AX = 8 * length
    mov cx, APP_TMR_BW
    sub cx, ax
    shr cx, 1                   ; every label fits, so this cannot go negative
    add cx, bp
    mov dx, di
    add dx, APP_TMR_LT
    call font_str

.out:
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; app_tmr_brect - one button's inclusive screen rect
; in:  AL = button index, BX = window ptr
; out: AX = x1, BX = y1, CX = x2, DX = y2
; clobbers: AX, BX, CX, DX (internal helper)
; -----------------------------------------------------------------------------
app_tmr_brect:
    call app_tmr_bpos           ; CX = x, DX = y
    mov ax, cx
    mov bx, dx
    add cx, APP_TMR_BW - 1
    add dx, APP_TMR_BH - 1
    ret

; -----------------------------------------------------------------------------
; app_tmr_bpos - one button's top-left, in screen coordinates
; in:  AL = button index, BX = window ptr
; out: CX = x, DX = y
; clobbers: flags (internal helper; AX is preserved - the caller's index)
; -----------------------------------------------------------------------------
app_tmr_bpos:
    push ax
    mov cl, APP_TMR_BW + APP_TMR_BGAP
    mul cl                      ; AX = index * pitch (both fit a byte)
    mov cx, ax
    call wm_content             ; AX = content left, DX = content top
    add cx, ax
    add cx, APP_TMR_BX
    add dx, APP_TMR_BY
    pop ax
    ret

; -----------------------------------------------------------------------------
; app_tmr_hit - which button is under a click? (SPEC.md 14)
; in:  BX = window ptr, CX = x, DX = y (screen)
; out: AL = button index, CF = 0; CF = 1 = no button (AL undefined)
; clobbers: AX, flags (internal helper)
;
; Derived from the same constants app_tmr_bpos draws from, so the hit-test
; and the pixels cannot part company - the fm_hit argument (SPEC.md 22.2).
; -----------------------------------------------------------------------------
app_tmr_hit:
    push bx
    push cx
    push dx
    push si
    mov si, dx                  ; SI = click y (wm_content wants DX)
    call wm_content             ; AX = content left, DX = content top
    sub cx, ax                  ; CX = content-relative x
    sub si, dx                  ; SI = content-relative y
    cmp si, APP_TMR_BY
    jl .miss
    cmp si, APP_TMR_BY + APP_TMR_BH
    jge .miss
    sub cx, APP_TMR_BX
    jl .miss
    xor bx, bx                  ; BX = the button being tested
.col:
    cmp cx, APP_TMR_BW
    jl .hit
    sub cx, APP_TMR_BW + APP_TMR_BGAP
    jl .miss                    ; landed in a gap between two buttons
    inc bx
    cmp bx, APP_TMR_NB
    jl .col
.miss:
    pop si
    pop dx
    pop cx
    pop bx
    stc
    ret
.hit:
    mov ax, bx
    pop si
    pop dx
    pop cx
    pop bx
    clc
    ret

; -----------------------------------------------------------------------------
; app_tmr_digits - position and draw the HH:MM:SS line
; in:  BX = window ptr, DI = time state ptr (gfx lock held)
; out: nothing
; clobbers: flags (SI is preserved - the timer task keeps its state ptr there
;           for life, so a clobber would scramble the state)
; -----------------------------------------------------------------------------
app_tmr_digits:
    push ax
    push cx
    push dx
    call app_tmr_pos            ; CX = string x, DX = string y
    call app_tmr_render
    pop dx
    pop cx
    pop ax
    ret

; -----------------------------------------------------------------------------
; app_tmr_pos - top-left of the 64x8 "HH:MM:SS" rect: centred across the
;               content, above the button row
; in:  BX = window ptr
; out: CX = x, DX = y
; clobbers: AX (internal helper)
; -----------------------------------------------------------------------------
app_tmr_pos:
    call wm_content             ; AX = content left, DX = content top
    mov cx, ax
    mov ax, [bx+W_W]
    sub ax, 2 + APP_TMR_DW      ; content width - string width
    shr ax, 1
    add cx, ax
    add dx, APP_TMR_DY
    ret

; -----------------------------------------------------------------------------
; app_tmr_render - format an instance's time as "HH:MM:SS" and draw it black
;                  on white, one 8x8 cell at a time
; in:  CX = x, DX = y, DI = time state ptr (gfx lock held by caller)
; out: nothing
; clobbers: AX (internal helper; SI is preserved - see app_tmr_digits)
;
; The white background is erased PER CELL rather than as one 64x8 rect, and
; that is a clipping requirement, not a style choice (SPEC.md 11.3): gfx_fill
; clips per pixel and font_char per whole cell, so a wide erase followed by
; glyphs can white out a band the glyphs then refuse to repaint - a Timer cut
; horizontally by another window's edge would blank the half you can see and
; keep blanking it twice a second. Per cell the two cannot disagree: a cell is
; either wholly drawable, and then erased and redrawn, or not, and then left
; entirely alone.
; -----------------------------------------------------------------------------
app_tmr_render:
    push si
    mov al, [ss:di+TMR_HRS]
    aam                         ; AH = tens, AL = ones
    add ax, 0x3030              ; both to ASCII, leading zero for free
    mov [app_tmr_str], ah
    mov [app_tmr_str+1], al
    mov byte [app_tmr_str+2], ':'
    mov al, [ss:di+TMR_MIN]
    aam
    add ax, 0x3030
    mov [app_tmr_str+3], ah
    mov [app_tmr_str+4], al
    mov byte [app_tmr_str+5], ':'
    mov al, [ss:di+TMR_SEC]
    aam
    add ax, 0x3030
    mov [app_tmr_str+6], ah
    mov [app_tmr_str+7], al
    mov byte [app_tmr_str+8], 0
    mov si, app_tmr_str
    push cx
.cell:
    mov al, [si]
    or al, al
    jz .done
    call app_tmr_cell
    add cx, 8
    inc si
    jmp short .cell
.done:
    pop cx
    pop si
    ret

; -----------------------------------------------------------------------------
; app_tmr_cell - one character: white 8x8 background, then the black glyph
; in:  AL = character, CX = x, DX = y (gfx lock held)
; out: nothing
; clobbers: flags (internal helper)
;
; wm_clip_test asks font_char's own question ahead of the erase - see
; app_tmr_render's banner. gfx_pen_live rather than a bare [gfx_color] store
; because a button drawn just before may have left [gfx_dis] set, and a
; flagged glyph is a checkerboard (SPEC.md 47 rule 1).
; -----------------------------------------------------------------------------
app_tmr_cell:
    push ax
    push bx
    push cx
    push dx
    mov ax, cx                  ; the cell rect, inclusive
    mov bx, dx
    add cx, 7
    add dx, 7
    call wm_clip_test
    jc .out                     ; not wholly drawable: erase nothing
    mov byte [gfx_color], CWHITE
    call gfx_fill               ; font backgrounds are transparent (SPEC.md 6)
    call gfx_pen_live
    pop dx
    pop cx
    pop bx
    pop ax
    jmp font_char               ; CX = x, DX = y, AL = char
.out:
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; =============================================================================
; Bounce
; =============================================================================

; -----------------------------------------------------------------------------
; app_bounce_task - per-instance task: 8x8 black square bouncing in the
;                   content, dies on request
; in:  DX = instance index (the spawn argument); never returns
; Ball position/velocity are content-relative words in the instance state.
;
; The ball ALWAYS steps (SPEC.md 14/11.3). Only the erase and the redraw are
; conditional: wm_clip_set under the lock either arms the visible region -
; and then the two 8x8 fills are cut to it, so a half-covered Bounce shows
; the ball crossing the half you can see - or answers CF = 1, and the frame
; steps invisibly. Stepping while covered is safe because app_bounce_paint
; draws from state, so the repaint on uncover shows the square where it now
; is rather than where it was when the window was buried. (Until SPEC.md
; 11.3 the frame was skipped without stepping, which is why a covered Bounce
; used to look frozen.) Edges: content w = 148, h = 111.
; -----------------------------------------------------------------------------
app_bounce_task:
    mov al, dl
    call inst_ptr               ; DI = our instance record
    mov bp, di                  ; BP = record for life
    mov si, [ds:bp+I_SPTR]      ; SI = ball state for life (ds: override:
                                ; BP addresses SS by default, SPEC.md 1)
.loop:
    mov ax, 2
    call task_sleep
    cmp byte [ds:bp+I_STATE], 2    ; close requested?
    je .die
    call gfx_lock
    mov bx, [ds:bp+I_WIN]
    test word [bx+W_FLAGS], 2   ; check under the lock (SPEC.md 14)
    jz .blind
    call wm_clip_set            ; CF = 1: not one visible pixel (SPEC 11.3)
    jc .blind

    mov di, si                  ; DI = ball state for app_ball_fill
    mov byte [gfx_color], CWHITE
    call app_ball_fill          ; erase at the old position
    call app_ball_step
    mov byte [gfx_color], CBLACK
    call app_ball_fill          ; draw at the new position
    jmp short .skip
.blind:
    call app_ball_step          ; nothing on screen to keep in step with
.skip:
    call gfx_unlock             ; ...which also disarms the clip (SPEC 11.3)
    jmp .loop

.die:
    mov di, bp
    jmp inst_task_die           ; never returns

; -----------------------------------------------------------------------------
; app_ball_step - advance one instance's ball, bouncing off the content edges
; in:  SI = ball state ptr
; out: nothing
; clobbers: nothing (flags only; internal helper)
; -----------------------------------------------------------------------------
app_ball_step:
    push ax
    mov ax, [ss:si+BAL_X]          ; step + bounce, x axis
    add ax, [ss:si+BAL_VX]
    jns .xhigh
    mov ax, 0                   ; hit the left wall
    neg word [ss:si+BAL_VX]
    jmp short .xdone
.xhigh:
    cmp ax, APP_BALL_XMAX
    jle .xdone
    mov ax, APP_BALL_XMAX       ; hit the right wall
    neg word [ss:si+BAL_VX]
.xdone:
    mov [ss:si+BAL_X], ax

    mov ax, [ss:si+BAL_Y]          ; step + bounce, y axis
    add ax, [ss:si+BAL_VY]
    jns .yhigh
    mov ax, 0                   ; hit the top
    neg word [ss:si+BAL_VY]
    jmp short .ydone
.yhigh:
    cmp ax, APP_BALL_YMAX
    jle .ydone
    mov ax, APP_BALL_YMAX       ; hit the bottom
    neg word [ss:si+BAL_VY]
.ydone:
    mov [ss:si+BAL_Y], ax
    pop ax
    ret

; -----------------------------------------------------------------------------
; app_bounce_paint - W_PAINT for a Bounce window
; in:  SI = window ptr (content already white-filled, gfx lock held)
; out: nothing
; clobbers: nothing (flags only)
; -----------------------------------------------------------------------------
app_bounce_paint:
    push bx
    push di

    mov bx, si                  ; instance state via the owner table
    call inst_of_win
    jc .done
    mov di, [di+I_SPTR]         ; DI = ball state
    mov byte [gfx_color], CBLACK
    call app_ball_fill

.done:
    pop di
    pop bx
    ret

; -----------------------------------------------------------------------------
; app_ball_fill - fill the 8x8 square at an instance's ball position
; in:  BX = window ptr, DI = ball state ptr; color from [gfx_color]
; out: nothing
; clobbers: nothing (flags only; internal helper)
; -----------------------------------------------------------------------------
app_ball_fill:
    push ax
    push bx
    push cx
    push dx

    call wm_content             ; AX = content left, DX = content top
    add ax, [ss:di+BAL_X]          ; AX = x1
    add dx, [ss:di+BAL_Y]
    mov bx, dx                  ; BX = y1
    mov cx, ax
    add cx, 7                   ; CX = x2
    add dx, 7                   ; DX = y2
    call gfx_fill

    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
section .lowbss                 ; LOW_SEG (SPEC.md 2.1): both state pools are
                                ; walked through a POINTER the instance record
                                ; hands over, never addressed by name, so they
                                ; cost one ss: prefix per access and nothing in
                                ; the kernel's own 64KB segment. SS is LOW_SEG
                                ; from kmain onwards and never changes, so the
                                ; prefix needs no setup and cannot be clobbered
app_tmr_pool:   resb 80         ; 10 x 8: TMR_HRS/MIN/SEC/RUN + LAST + ACC
app_ball_pool:  resb 80         ; 10 x 8: BAL_X/Y/VX/VY

section .bss

app_tmr_str:    resb 9          ; "HH:MM:SS",0 scratch (drawn under the lock)

section .text
