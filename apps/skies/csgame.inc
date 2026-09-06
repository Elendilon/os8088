; =============================================================================
; os8088 - apps/skies/csgame.inc
;
; THE SESSION (SPEC.md 88.8): the fsx bracket, the polled input model a
; bracket has instead of events, the frame, and the panel (88.9).
; =============================================================================

; -----------------------------------------------------------------------------
; cs_cmd_fly - take the machine (SPEC.md 53.1)
; in:  gfx lock held (menu / key / click context).  preserves all registers
; -----------------------------------------------------------------------------
cs_cmd_fly:
    push ax
    push bx
    push cx
    cmp byte [cs_want], CSB_NONE
    je .out                         ; the same predicate the menu greyed on
    mov ax, cs_fsx_main
    mov bx, [cs_win]
    xor cx, cx                      ; no worker to keep: this loop IS the flight
    call OSAPI_FSX_RUN              ; the kernel repaints the desktop on the
.out:                               ; way out (SPEC.md 53.6)
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; cs_fsx_main - the exclusive main (SPEC.md 53.1)
; in:  SI = our window, ES = KERNEL_SEG, DS = CS = ours, gfx lock held for the
;      whole session, every other task frozen
; -----------------------------------------------------------------------------
cs_fsx_main:
    push ds
    pop es
    mov di, cs_fsi
    mov al, [cs_fsxm]
    call OSAPI_FSX_MODE
    jc .out                         ; refused: the desktop is untouched
    mov al, [cs_want]
    mov [cs_back], al
    call cs_r_setup
    jc .out
    call cs_glyphs
    call cs_clearall
    call cs_runway_build            ; the runway, from the record
    cmp byte [cs_inited], 0         ; the first flight starts on the runway;
    jne .keep                       ; a later one carries on where it was
    call cs_reset
.keep:
    mov byte [cs_par], 0
    mov byte [cs_quit], 0
    mov byte [cs_pause], 0
    mov word [cs_tone], 0
    mov ax, [cs_vw]                 ; the panel's horizontal scale, in eighths
    mov bx, 8
    mul bx
    mov bx, 320
    div bx
    mov [cs_hsx], ax
    call OSAPI_GET_TICKS
    mov [cs_last], ax
%ifdef CSDIAG
    call cs_diag_on                 ; the watchdog, for the bracket's length
%endif                              ; (SPEC.md 88.14)
.loop:
    call cs_input
    cmp byte [cs_quit], 0
    jne .leave
    call cs_steps                   ; CX = ticks since the last frame
    jcxz .draw
    cmp byte [cs_pause], 0
    jne .draw
.sim:
    push cx
    call cs_stick                   ; THE STICK, ONCE A TICK (SPEC.md
    call cs_step                    ; 88.7.5.1): cs_input runs once a FRAME,
    call cs_sound_step              ; which is 137 ms on Mode X, so a tap
    pop cx                          ; shorter than that was never seen at all
    loop .sim
.draw:
    call cs_render
    jmp short .loop
.leave:
%ifdef CSDIAG
    call cs_diag_off
%endif
    xor ax, ax                      ; the engine off with the mode
    xor cx, cx
    mov dl, 0x40
    call OSAPI_SND_TONE
.out:
    ret

; -----------------------------------------------------------------------------
; cs_stick - the two attitude axes into [cs_kpitch] and [cs_kroll]
;            (SPEC.md 88.7.5.1). Clobbers AX, BX
;
; Read ONCE A TICK and not once a frame, which is where it used to live.
; OSAPI_KEY_DOWN is a LEVEL read - the SDK says so, and there is no latched
; form - so a press that came and went between two polls never happened, and
; a poll a frame is 137 ms on Mode X. The stick is the one input where that
; is the difference between a tap being a nudge and a tap being nothing;
; the throttle, the rudder and the brake stay on the frame, where three
; times the sampling would only make them three times as fast.
;
; Four far calls, 46.7 us each: 187 us a tick, so 374 us of a 137 ms frame
; on the two extra ticks - 0.27%.
; -----------------------------------------------------------------------------
cs_stick:
    push bx
    xor bl, bl
    mov al, KSC_UP                  ; up = nose down, down = nose up: the
    call OSAPI_KEY_DOWN             ; stick, as in every flight simulator
    jnc .p1
    dec bl
.p1:
    mov al, KSC_DOWN
    call OSAPI_KEY_DOWN
    jnc .p2
    inc bl
.p2:
    mov al, [cs_waspitch]           ; the PREVIOUS tick's level read...
    mov [cs_waspitch], bl           ; ...and this one's, for the next tick
    or bl, bl                       ; up? then a LATCHED press stands in for
    jnz .p3                         ; it, once (88.7.5.2)
    or al, al                       ; ...unless the key was DOWN last tick,
    jnz .p3                         ; where the latch is a typematic repeat
    mov bl, [cs_tappitch]           ; of a hold that has just ended and
.p3:                                ; spending it overshoots by a tick
    mov byte [cs_tappitch], 0
    mov [cs_kpitch], bl
    xor bl, bl
    mov al, KSC_LEFT
    call OSAPI_KEY_DOWN
    jnc .r1
    dec bl
.r1:
    mov al, KSC_RIGHT
    call OSAPI_KEY_DOWN
    jnc .r2
    inc bl
.r2:
    mov al, [cs_wasroll]
    mov [cs_wasroll], bl
    or bl, bl
    jnz .r3
    or al, al
    jnz .r3
    mov bl, [cs_taproll]
.r3:
    mov byte [cs_taproll], 0
    mov [cs_kroll], bl
    pop bx
    ret

; -----------------------------------------------------------------------------
; cs_steps - how many SIMULATION steps this frame owes, and the wait if none
; out: CX = 1..CS_MAXSTEP.  clobbers AX, BX  (SPEC.md 85.6's tk_steps)
; -----------------------------------------------------------------------------
cs_steps:
    call OSAPI_GET_TICKS
    mov bx, ax
    sub ax, [cs_last]
    jnz .have
    mov al, FSXW_TICK               ; nothing owing: do not burn the machine
    call OSAPI_FSX_WAIT             ; drawing a frame identical to the last
    call OSAPI_GET_TICKS
    mov bx, ax
    sub ax, [cs_last]
.have:
    mov [cs_last], bx
    cmp ax, CS_MAXSTEP
    jbe .ok
    mov ax, CS_MAXSTEP
.ok:
    mov cx, ax
    ret

; -----------------------------------------------------------------------------
; cs_clearall - both pages, or the whole shadow, once at entry; and the panel
;               keys stale, so the first frame draws every instrument
; -----------------------------------------------------------------------------
cs_clearall:
    push ds
    pop es
    mov di, cs_pkeys
    mov cx, 2 * 16
    mov ax, 0xFFFF
    cld
    rep stosw
    mov byte [cs_pfirst], 3         ; both pages owe a panel ground
    mov di, cs_rowkind              ; every view row unknown and dirty, so
    mov cx, CS_MAXROW               ; the first frame fills and carries all
    mov al, 0x83
    rep stosb
    mov di, cs_span0                ; ...over empty spans
    mov cx, CS_MAXROW * 2
    mov ax, 0x00FF
    rep stosw
    mov es, [cs_tseg]
    cmp byte [cs_back], CSB_MODEX
    jne .flat
    mov dx, 0x3C4
    mov ax, 0x0F02
    out dx, ax
    xor di, di
    mov cx, 240 * 80 * 2 / 2        ; both pages, in words
    xor ax, ax
    rep stosw
    ret
.flat:
    xor di, di
    mov cx, CS_SHSEG / 2
    xor ax, ax
    rep stosw
    ret

; -----------------------------------------------------------------------------
; cs_input - a bracket dispatches no events, so this is the whole input model
;            (SPEC.md 53.1, 85.6's two readers)
; -----------------------------------------------------------------------------
cs_input:
    push ax
    mov byte [cs_hzhold], 0         ; ONCE A FRAME (SPEC.md 88.7.5.2): a
                                    ; capture holds its axis for the rest of
                                    ; the frame it happened in and no longer
    push bx
    push cx
    push dx
.keys:
    mov ah, 1
    int 0x16
    jz .held
    xor ah, ah
    int 0x16
    or al, al                       ; --- AN EXTENDED KEY: AL is 0 and AH the
    jnz .chars                      ; scan code, which is where the ARROWS are
    jmp .ext                        ; (a short jump will not reach it)
.chars:
    cmp al, 27                      ; Esc
    je .quit
    cmp al, 'f'
    je .quit
    cmp al, 'F'
    je .quit
    cmp al, 'p'
    je .pause
    cmp al, 'P'
    je .pause
    cmp al, 'r'
    je .reset
    cmp al, 'R'
    je .reset
    cmp al, 'm'
    je .mute
    cmp al, 'M'
    je .mute
    call cs_hotkey                  ; --- the settings, in flight (88.13.5)
    jnc .keys
    jmp .keys
.ext:
    ; --- A STICK PRESS, LATCHED (SPEC.md 88.7.5.2). This is Arkanoid's
    ; answer and it is the half Clear Skies did not have: int 16h is an
    ; EVENT, held in the BIOS type-ahead buffer, so a press cannot be missed
    ; however brief - where OSAPI_KEY_DOWN is a LEVEL read and a press that
    ; came and went between two polls never happened. The level read is what
    ; sees a HOLD, which int 16h cannot (no key-up, and a typematic delay
    ; before the repeats); the two are complements and the aeroplane wants
    ; both. cs_stick spends the latch on the next tick it finds the key up.
    mov bl, -1
    cmp ah, KSC_LEFT
    je .taproll
    mov bl, 1
    cmp ah, KSC_RIGHT
    je .taproll
    mov bl, -1
    cmp ah, KSC_UP
    je .tappitch
    mov bl, 1
    cmp ah, KSC_DOWN
    jne .keys
.tappitch:
    mov [cs_tappitch], bl
    jmp .keys
.taproll:
    mov [cs_taproll], bl
    jmp .keys
.mute:
    xor byte [cs_sound], 1
    jmp short .keys
.reset:
    call cs_reset
    jmp short .keys
.pause:
    xor byte [cs_pause], 1
    mov byte [cs_msg], CSG_PAUSED
    cmp byte [cs_pause], 0
    jne .keys
    mov byte [cs_msg], CSG_NONE
    jmp .keys
.quit:
    mov byte [cs_quit], 1
    jmp .done

.held:                              ; THE HELD KEYS ARE LATCHED HERE AND SPENT
                                    ; ON THE TICK (SPEC.md 85.6.4). The two
                                    ; STICK axes are NOT read here: cs_stick
                                    ; is the sim loop's now (88.7.5.1) and
                                    ; calling it here as well would spend the
                                    ; tap latch a tick BEFORE the first
                                    ; cs_step, which is the tap going missing
                                    ; (88.7.5.2)
    xor bl, bl
    mov al, CS_KA
    call OSAPI_KEY_DOWN
    jnc .y1
    dec bl
.y1:
    mov al, CS_KD
    call OSAPI_KEY_DOWN
    jnc .y2
    inc bl
.y2:
    mov [cs_kyaw], bl
    xor bl, bl
    mov al, CS_KS
    call OSAPI_KEY_DOWN
    jnc .t1
    dec bl
.t1:
    mov al, CS_KW
    call OSAPI_KEY_DOWN
    jnc .t2
    inc bl
.t2:
    mov [cs_kthr], bl
    xor bl, bl
    mov al, CS_KB
    call OSAPI_KEY_DOWN
    jnc .b1
    inc bl
.b1:
    mov [cs_kbrake], bl
.done:
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; cs_scrclear - the whole framebuffer, black (SPEC.md 88.13.4)
;
; cs_clearall zeroes the SHADOW, and the blit copies only the view's byte
; columns out of it - so shrinking the view leaves whatever the larger one
; had put in the pixels BESIDE it, which is a band of last size's ground
; standing either side of the picture until the mode is set again. Mode X
; needs none of this: its pages are the framebuffer and cs_clearall has
; already cleared both.
; -----------------------------------------------------------------------------
cs_scrclear:
    cmp byte [cs_back], CSB_MODEX
    je .out
    push ax
    push cx
    push di
    push es
    mov es, [cs_fsi + FSI_SEG]
    xor di, di
    mov cx, 0x4000 / 2              ; THE WHOLE WINDOW, not stride x rows: a
    cmp byte [cs_back], CSB_HERC    ; Hercules page is four interleaved banks
    jne .go                         ; of 8KB and only 7,830 bytes of each are
    mov cx, 0x8000 / 2              ; rows, so the arithmetic leaves the tail
.go:                                ; of the last bank standing
    xor ax, ax
    cld
    rep stosw
    pop es
    pop di
    pop cx
    pop ax
.out:
    ret

; -----------------------------------------------------------------------------
; cs_hotkey - a settings key inside the bracket (SPEC.md 88.13.5)
; in:  AL = the character; out: CF = 1 it was one of ours. Clobbers AX, BX, CX
;
;   -/+   the view's Size, down and up      1 2 3  Buildings: few, some, all
;   4 5 6 the three fills, each a toggle    7 8 9  Detail: near, moderate, far
;
; A key that changes what is DRAWN costs the next frame and nothing after it,
; so it is one store. Size is the exception - the view's geometry, its byte
; columns, the projection tables and the span sets all derive from it - so
; that one re-runs the raster's own setup, which is idempotent and reuses the
; shadow claim it already holds (88.13.4). Neither costs a cycle while
; flying: no frame reads a setting more than the frame it draws.
; -----------------------------------------------------------------------------
cs_hotkey:
    cmp al, '-'
    je .zdown
    cmp al, '_'
    je .zdown
    cmp al, '+'
    je .zup
    cmp al, '='
    je .zup
    cmp al, '1'
    jb .no
    cmp al, '9'
    ja .no
    sub al, '1'
    cmp al, 3
    jb .bld
    cmp al, 6
    jb .fill
    sub al, 6                       ; 7 8 9: Detail
    mov [cs_setlod], al
    jmp short .yes
.bld:                               ; 1 2 3: Buildings
    mov [cs_setbld], al
    call cs_skipclr                 ; every object is looked at again, or one
    jmp short .yes                  ; the cull dropped stays dropped (88.5.2)
.fill:                              ; 4 5 6: one fill each, toggled
    sub al, 3                       ; 0, 1 or 2
    mov cl, al
    mov al, 1
    shl al, cl
    xor [cs_setfill], al
    jmp short .yes
.zdown:
    mov al, [cs_setsize]
    or al, al
    jz .yes
    dec al
    jmp short .size
.zup:
    mov al, [cs_setsize]
    cmp al, CSZ_FULL
    jae .yes
    inc al
.size:
    mov [cs_setsize], al
    call cs_r_setup                 ; the whole geometry follows the size
    call cs_clearall                ; ...and what was on the glass is stale
    call cs_scrclear                ; ...INCLUDING THE PIXELS BESIDE THE VIEW
.yes:
    stc
    ret
.no:
    clc
    ret

; -----------------------------------------------------------------------------
; cs_render - one frame (SPEC.md 88.8)
; -----------------------------------------------------------------------------
cs_render:
    inc word [cs_frames]            ; the only instrumentation in here, and
    call cs_r_begin                 ; tests/skies.py is what reads it
    call cs_matrix
    mov ax, [cs_px+1]               ; the eye, in whole metres
    mov [cs_ex], ax
    cwd
    mov [cs_exh], dx
    mov ax, [cs_pz+1]
    mov [cs_ez], ax
    cwd
    mov [cs_ezh], dx
    mov ax, [cs_py+1]
    mov si, [cs_plane]
    add ax, [si + CSP_EYE]
    mov [cs_ey], ax
    call cs_skyground
    call cs_scene
    call cs_panel
    call cs_r_end
    ret

; =============================================================================
; The panel (SPEC.md 88.9): items keyed on what they show, redrawn on change
; =============================================================================
CS_PI_SPD  equ 0
CS_PI_ALT  equ 1
CS_PI_HDG  equ 2
CS_PI_ADI  equ 3                    ; the attitude indicator (88.9.2)
CS_PI_THR  equ 4
CS_PI_STATE equ 5
CS_PI_BAR  equ 6
CS_PI_MSG  equ 7
CS_PI_VS   equ 8                    ; the VARIOMETER (SPEC.md 88.7.6) - a
                                    ; cockpit that has none puts its cell at
                                    ; 0,0 and cs_d_vs returns at once
CS_PI_N    equ 9

; the layout is the cockpit's (cspanel.inc): x at 320 wide through
; cs_hscalex, rows below the view

; -----------------------------------------------------------------------------
; cs_panel - every item whose key moved, and the ground under them the first
;            time a target is drawn on
; -----------------------------------------------------------------------------
cs_panel:
    mov al, [cs_par]
    and al, 1
    cmp byte [cs_back], CSB_MODEX
    je .pg
    xor al, al                      ; one target: page 0's keys
.pg:
    mov [cs_ppage], al
    ; --- the instruments read the aeroplane every CS_PRATE ticks, not every
    ;     frame (88.9.1): an altitude in feet changes every tick in a climb,
    ;     and nine glyphs a change at the frame rate was a tenth of the frame
    mov byte [cs_pgate], 1
    mov ax, [cs_last]
    sub ax, [cs_plast]
    cmp ax, CS_PRATE
    jae .read
    mov byte [cs_pgate], 0
    jmp short .first
.read:
    mov ax, [cs_last]
    mov [cs_plast], ax
.first:
    mov al, [cs_ppage]              ; (the gate spent AX)
    mov ah, 1
    mov cl, al
    shl ah, cl
    test [cs_pfirst], ah
    jz .items
    mov byte [cs_pgate], 1          ; the first frame draws everything
    not ah                          ; this target's first frame: the cockpit
    and [cs_pfirst], ah
    call cs_pface                   ; (88.9.2)
    push ds                         ; ...and every key on this page stale
    pop es
    mov al, [cs_ppage]
    xor ah, ah
    mov cl, 5
    shl ax, cl
    add ax, cs_pkeys
    mov di, ax
    mov cx, 16
    mov ax, 0xFFFF
    cld
    rep stosw
.items:
    xor bx, bx
.i:
    push bx
    call cs_pitem
    pop bx
    inc bx
    cmp bx, CS_PI_N
    jb .i
    ret

; -----------------------------------------------------------------------------
; cs_pitem - BX = an item: SAMPLE it on the gate, and PAINT it on any page
;            that has not got that value on it yet (SPEC.md 88.9.4)
;
; The two halves are separate on purpose and were not, which is what made a
; Mode X altimeter read 1,683 feet one frame and 1,666 the next, for ever.
; The gate is in TICKS and the page is the frame's PARITY, so a gate frame
; lands on whichever page happens to be current and the other one keeps
; whatever it last had - and with the two rates near each other the same
; page can win several gates in a row. Both pages then hold real readings,
; taken seconds apart, and the flip shows them alternately.
;
; So the gate now decides when the aeroplane is READ, into one latched set
; both pages share, and each page's own cache decides whether it still needs
; painting. A change is drawn twice - once per page, on consecutive frames -
; which is what a double buffer costs and what it was quietly not paying.
; One target (Hercules, CGA) is unaffected: cs_ppage is always 0 there, and
; this was never visible on either.
; -----------------------------------------------------------------------------
cs_pitem:
    mov [cs_pcur], bx
    cmp bx, CS_PI_STATE             ; the state and the message NEVER wait:
    je .now                         ; a stall or a crash has to show at once
    cmp bx, CS_PI_MSG
    je .now
    cmp byte [cs_pgate], 0
    je .paint                       ; between gates the latched value stands
.now:
    call cs_pkey                    ; AX = what it would show now...
    mov bx, [cs_pcur]
    shl bx, 1
    mov [cs_pshow + bx], ax         ; ...latched, ONE set for both pages
.paint:
    mov bx, [cs_pcur]
    shl bx, 1
    mov ax, [cs_pshow + bx]
    mov [cs_pkeyv], ax
    mov al, [cs_ppage]
    xor ah, ah
    mov cl, 5
    shl ax, cl                      ; 32 bytes a page of keys
    add bx, ax
    mov ax, [cs_pkeyv]
    cmp ax, [cs_pkeys + bx]
    je .same
    mov [cs_pkeys + bx], ax
    mov bx, [cs_pcur]
    shl bx, 1
    jmp [cs_pdraw + bx]
.same:
    ret

; cs_pkey - the key of item [cs_pcur]: the value it would show
cs_pkey:
    mov bx, [cs_pcur]
    shl bx, 1
    jmp [cs_pkeyp + bx]

cs_pkeyp:  dw cs_k_spd, cs_k_alt, cs_k_hdg, cs_k_adi, cs_k_thr, cs_k_state
           dw cs_k_thr, cs_k_msg, cs_k_vs
cs_pdraw:  dw cs_d_spd, cs_d_alt, cs_d_hdg, cs_d_adi, cs_d_thr, cs_d_state
           dw cs_d_bar, cs_d_msg, cs_d_vs

; --- the keys -----------------------------------------------------------------
cs_k_spd:                           ; knots: v(16.7) x 1.944 / 128
    mov ax, [cs_spd]
    mov bx, 996
    mul bx
    mov ax, dx
    ret
cs_k_alt:                           ; feet: metres x 3.281
    mov ax, [cs_py+1]
    mov bx, 210
    mul bx
    mov cl, 6
    call cs_shr32
    ret
cs_k_hdg:                           ; degrees: hdg x 360 / 65536
    mov ax, [cs_hdg]
    mov bx, 360
    mul bx
    mov ax, dx
    ret
cs_k_thr:
    mov ax, [cs_thr]
    ret
cs_k_state:
    mov al, [cs_state]
    mov ah, [cs_stall]
    or ah, [cs_onwater]             ; ...and WHICH ground, so the strip
    shl ah, 1                       ; repaints when a hull leaves the water
    or ah, [cs_stall]               ; (88.7.7)
    ret
cs_k_msg:
    mov al, [cs_msg]
    mov ah, [cs_crashwhy]           ; the low byte of the string's address
    ret                             ; tells crashes apart

; cs_shr32 - DX:AX >>= CL (CL < 16). Clobbers CX.
cs_shr32:
    or cl, cl
    jz .o
.s:
    shr dx, 1
    rcr ax, 1
    dec cl
    jnz .s
.o:
    ret

; --- the draws: every one letters opaquely at a fixed width -------------------
; in: [cs_pkeyv] = the key just cached

; cs_pnum - AX = a value, CL = digits, SI = the label; letters "LABEL nnn" at
; DX = the row, BX = the x at 320 wide
; cs_pnum - AX = the value, CL = digits, SI = the label, BX/DX = the cell:
; THE DIGITS ONLY, four cells along, because cs_plabels drew the label with
; the cockpit and it has not changed since (SPEC.md 88.9.4). SI is taken and
; ignored so the callers read as they did; cs_pnuml is the form that letters
; the label too, which is the variometer's, its label being its sign.
cs_pnum:
    add bx, 4 * 8                   ; a cell is 8 wide at 320, on every adapter
    push ax
    mov di, cs_numbuf
    pop ax
    call cs_utoa
    mov si, cs_numbuf
    jmp cs_pline

cs_pnuml:
    push si
    push ax
    mov di, cs_numbuf
    call cs_strcpy                  ; the label...
    pop ax
    call cs_utoa                    ; ...and the number after it
    pop si
    mov si, cs_numbuf
    jmp cs_pline

; cs_pline - SI = a string, BX = the x at 320 wide, DX = the row (below the
; view); letters it in the panel's ink
cs_pline:
    mov al, CSI_PFG
    call cs_setink
cs_pline_ink:
    push dx                         ; cs_hscalex multiplies, and DX is the row
    mov ax, bx
    call cs_hscalex
    pop dx
    mov cx, ax
    add dx, [cs_pany]
    call cs_text
    ret

; cs_hscalex - AX = an x at 320 wide; out AX = it in this box. Clobbers DX.
cs_hscalex:
    cmp word [cs_hsx], 8
    je .same
    imul word [cs_hsx]
    sar ax, 1
    sar ax, 1
    sar ax, 1
.same:
    ret

; cs_strcpy - SI -> DI, up to and excluding the NUL; DI left on it
cs_strcpy:
    lodsb
    or al, al
    jz .d
    mov [di], al
    inc di
    jmp short cs_strcpy
.d:
    ret

cs_d_spd:
    mov bx, CS_PI_SPD
    call cs_pcell
    mov ax, [cs_pkeyv]
    mov cl, 3
    mov si, cs_s_spd
    jmp cs_pnum
cs_d_alt:
    mov bx, CS_PI_ALT
    call cs_pcell
    mov ax, [cs_pkeyv]
    mov cl, 5
    mov si, cs_s_alt
    jmp cs_pnum
cs_d_hdg:
    mov bx, CS_PI_HDG
    call cs_pcell
    mov ax, [cs_pkeyv]
    mov cl, 3
    mov si, cs_s_hdg
    jmp cs_pnum
cs_k_vs:                            ; the VARIOMETER: tenths of a metre a
    mov ax, [cs_vs]                 ; second, and its SIGN in the high byte -
    mov bx, 10                      ; the key has to change when the needle
    imul bx                         ; crosses zero or the cache holds the
    mov bx, 128                     ; wrong label (88.7.6)
    idiv bx
    ret

cs_d_vs:
    mov bx, CS_PI_VS
    call cs_pcell
    or bx, bx
    jz .none                        ; this cockpit has no variometer
    mov ax, [cs_pkeyv]
    mov si, cs_s_up
    or ax, ax
    jns .up
    neg ax
    mov si, cs_s_dn
.up:
    cmp ax, 999
    jle .n
    mov ax, 999
.n:
    mov cl, 3
    jmp cs_pnuml                    ; the vario letters its own label: UP or
.none:                              ; DN is the reading's SIGN (88.9.4)
    ret

cs_d_thr:
    mov bx, CS_PI_THR
    call cs_pcell
    mov ax, [cs_pkeyv]
    mov cl, 3
    mov si, cs_s_thr
    jmp cs_pnum
cs_d_state:
    mov ax, [cs_pkeyv]
    mov si, cs_s_ground
    cmp al, CS_ST_GROUND
    jne .air
    cmp byte [cs_onwater], 0
    je .s
    mov si, cs_s_water
    jmp short .s
.air:
    mov si, cs_s_crash
    cmp al, CS_ST_CRASH
    je .s
    mov si, cs_s_flying
    or ah, ah
    jz .s
    mov si, cs_s_stalled
.s:
    push si
    mov bx, CS_PI_STATE
    call cs_pcell
    pop si
    jmp cs_pline
cs_d_bar:                           ; the throttle bar: 0..100 in its slot
    mov bx, CS_PI_BAR
    call cs_pcell                   ; BX = its left end, DX = its top row
    or bx, bx
    jz .none                        ; a glider has no throttle to draw (88.7.6)
    mov [cs_pbarx], bx
    add dx, [cs_pany]
    mov [cs_pbary], dx
    mov si, [cs_plane]
    mov si, [si + CSP_COCKPIT]
    mov ax, [si + CSK_BARW]
    mov [cs_pbarw], ax
    mov al, CSI_PBG                 ; the whole slot in the ground first...
    call cs_setink
    mov ax, [cs_pbarx]
    add ax, [cs_pbarw]
    call cs_hscalex
    mov cx, ax
    mov ax, [cs_pbarx]
    call cs_hscalex
    mov bx, [cs_pbary]
    mov dx, bx
    add dx, 5
    call cs_prect
    mov ax, [cs_pkeyv]              ; ...then the lit part: 100 is the width
    or ax, ax
    jz .none
    mul word [cs_pbarw]
    mov bx, 100
    div bx
    add ax, [cs_pbarx]
    call cs_hscalex
    mov cx, ax
    mov ax, [cs_pbarx]
    call cs_hscalex
    cmp ax, cx
    jg .none
    mov al, CSI_PHI
    call cs_setink
    mov ax, [cs_pbarx]
    call cs_hscalex
    mov bx, [cs_pbary]
    mov dx, bx
    add dx, 5
    call cs_prect
.none:
    ret

cs_d_msg:                           ; the message line, padded to 40 cells
    mov di, cs_msgbuf
    mov al, [cs_msg]
    xor ah, ah
    mov bx, ax
    shl bx, 1
    mov si, [cs_msgtab + bx]
    call cs_strcpy
    cmp byte [cs_msg], CSG_CRASH
    jne .pad
    mov si, [cs_crashwhy]
    call cs_strcpy
.pad:
    mov al, ' '
    mov cx, cs_msgbuf + 40
    sub cx, di
    jle .term
    cld
    push ds
    pop es
    rep stosb
.term:
    mov byte [cs_msgbuf + 40], 0
    mov al, CSI_PHI
    cmp byte [cs_msg], CSG_CRASH
    je .ink
    cmp byte [cs_msg], CSG_STALL
    je .ink
    mov al, CSI_PFG
.ink:
    call cs_setink
    mov si, cs_msgbuf
    mov ax, [cs_vw]
    sub ax, 320
    shr ax, 1                       ; 40 cells, centred in the box
    mov cx, ax
    mov bx, CS_PI_MSG
    push cx
    call cs_pcell
    pop cx
    add dx, [cs_pany]
    call cs_text
    ret

cs_s_spd:    db 'SPD ', 0
cs_s_alt:    db 'ALT ', 0
cs_s_hdg:    db 'HDG ', 0
cs_s_thr:    db 'THR ', 0
cs_s_up:     db 'UP  ', 0        ; the variometer's two labels: a needle
cs_s_dn:     db 'DN  ', 0        ; and not a signed number (88.7.6)
cs_s_ground: db 'ON THE GROUND', 0
cs_s_water:  db 'ON THE WATER ', 0
cs_s_flying: db 'FLYING       ', 0
cs_s_stalled: db 'STALL        ', 0
cs_s_crash:  db 'CRASHED      ', 0

cs_msgtab:   dw cs_g_none, cs_g_takeoff, cs_g_stall, cs_g_landed
             dw cs_g_crash, cs_g_paused, cs_g_edge, cs_g_release
             dw cs_g_splash
cs_g_none:   db 0
cs_g_takeoff: db 'FULL THROTTLE, PULL BACK AT 55 KNOTS', 0
cs_g_stall:  db 'STALL - NOSE DOWN, POWER ON', 0
cs_g_landed: db 'LANDED', 0
cs_g_crash:  db 'CRASHED INTO ', 0
cs_g_paused: db 'PAUSED', 0
cs_g_edge:   db 'THE EDGE OF THE WORLD - TURN BACK', 0
cs_g_release: db 'TOW RELEASED - NOSE DOWN FOR 43 KNOTS', 0
cs_g_splash: db 'DOWN ON ', 0    ; ...and the water's own name after it
