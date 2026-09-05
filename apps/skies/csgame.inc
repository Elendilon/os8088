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
    call cs_step
    call cs_sound_step
    pop cx
    loop .sim
.draw:
    call cs_render
    jmp short .loop
.leave:
    xor ax, ax                      ; the engine off with the mode
    xor cx, cx
    mov dl, 0x40
    call OSAPI_SND_TONE
.out:
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
    push bx
    push cx
    push dx
.keys:
    mov ah, 1
    int 0x16
    jz .held
    xor ah, ah
    int 0x16
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
    jne .keys
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
    jmp short .keys
.quit:
    mov byte [cs_quit], 1
    jmp .done

.held:                              ; THE HELD KEYS ARE LATCHED HERE AND SPENT
    xor bl, bl                      ; ON THE TICK (SPEC.md 85.6.4)
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
    mov [cs_kroll], bl
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
CS_PI_VS   equ 3
CS_PI_THR  equ 4
CS_PI_STATE equ 5
CS_PI_BAR  equ 6
CS_PI_MSG  equ 7
CS_PI_KEYS equ 8
CS_PI_N    equ 9

; the layout, at 320 wide (x scaled by cs_hscalex) and rows below the view
CS_PR1    equ 4
CS_PR2    equ 16
CS_PR3    equ 30                    ; the throttle bar, six rows
CS_PR4    equ 44
CS_PR5    equ 60

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
    mov ah, 1
    mov cl, al
    shl ah, cl
    test [cs_pfirst], ah
    jz .items
    mov byte [cs_pgate], 1          ; the first frame draws everything
    not ah                          ; this target's first frame: the ground
    and [cs_pfirst], ah
    mov al, CSI_PBG
    call cs_setink
    xor ax, ax
    mov bx, [cs_pany]
    mov cx, [cs_vw]
    dec cx
    mov dx, [cs_vh]
    dec dx
    call cs_prect
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

; cs_pitem - BX = an item: its key now, against the cache; draw on a change
cs_pitem:
    mov [cs_pcur], bx
    cmp bx, CS_PI_VS                ; the four readings wait for the gate;
    ja .now                         ; a message or the state never does
    cmp byte [cs_pgate], 0
    je .same
.now:
    call cs_pkey                    ; AX = the item's key
    mov [cs_pkeyv], ax
    mov bx, [cs_pcur]
    shl bx, 1
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

cs_pkeyp:  dw cs_k_spd, cs_k_alt, cs_k_hdg, cs_k_vs, cs_k_thr, cs_k_state
           dw cs_k_thr, cs_k_msg, cs_k_one
cs_pdraw:  dw cs_d_spd, cs_d_alt, cs_d_hdg, cs_d_vs, cs_d_thr, cs_d_state
           dw cs_d_bar, cs_d_msg, cs_d_keys

; --- the keys -----------------------------------------------------------------
cs_k_spd:                           ; knots: v(16.8) x 1.944 / 256
    mov ax, [cs_spd]
    mov bx, 498
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
cs_k_vs:                            ; feet a minute, to the nearest 50:
    mov ax, [cs_vs]                 ; vs(16.8) x 196.85 / 256 = vs x 0.769
    mov bx, 788
    imul bx
    mov al, ah                      ; >> 10: a byte and two more
    mov ah, dl
    sar ax, 1
    sar ax, 1
    cwd
    mov bx, 50
    idiv bx
    ret                             ; AX = fpm / 50, signed
cs_k_thr:
    mov ax, [cs_thr]
    ret
cs_k_state:
    mov al, [cs_state]
    mov ah, [cs_stall]
    ret
cs_k_msg:
    mov al, [cs_msg]
    mov ah, [cs_crashwhy]           ; the low byte of the string's address
    ret                             ; tells crashes apart
cs_k_one:
    mov ax, 1
    ret

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
cs_pnum:
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
    mov ax, [cs_pkeyv]
    mov cl, 3
    mov si, cs_s_spd
    mov bx, 8
    mov dx, CS_PR1
    jmp cs_pnum
cs_d_alt:
    mov ax, [cs_pkeyv]
    mov cl, 5
    mov si, cs_s_alt
    mov bx, 72
    mov dx, CS_PR1
    jmp cs_pnum
cs_d_hdg:
    mov ax, [cs_pkeyv]
    mov cl, 3
    mov si, cs_s_hdg
    mov bx, 152
    mov dx, CS_PR1
    jmp cs_pnum
cs_d_vs:
    mov ax, [cs_pkeyv]              ; fpm / 50, signed: sign, then x 50
    mov di, cs_numbuf
    mov si, cs_s_vs
    call cs_strcpy
    mov byte [di], '+'
    or ax, ax
    jns .p
    neg ax
    mov byte [di], '-'
.p:
    inc di
    mov bx, 50
    mul bx
    mov cl, 4
    call cs_utoa
    mov si, cs_numbuf
    mov bx, 216
    mov dx, CS_PR1
    jmp cs_pline
cs_d_thr:
    mov ax, [cs_pkeyv]
    mov cl, 3
    mov si, cs_s_thr
    mov bx, 8
    mov dx, CS_PR2
    call cs_pnum
    ret
cs_d_state:
    mov ax, [cs_pkeyv]
    mov si, cs_s_ground
    cmp al, CS_ST_GROUND
    je .s
    mov si, cs_s_crash
    cmp al, CS_ST_CRASH
    je .s
    mov si, cs_s_flying
    or ah, ah
    jz .s
    mov si, cs_s_stalled
.s:
    mov bx, 80
    mov dx, CS_PR2
    jmp cs_pline
cs_d_bar:                           ; the throttle bar: 0..100 at 320 wide
    mov al, CSI_PBG                 ; the whole slot in the ground first...
    call cs_setink
    mov ax, 8
    call cs_hscalex
    mov si, ax
    mov ax, 109
    call cs_hscalex
    mov cx, ax
    mov ax, si
    mov bx, [cs_pany]
    add bx, CS_PR3
    mov dx, bx
    add dx, 5
    call cs_prect
    mov ax, [cs_pkeyv]              ; ...then the lit part
    or ax, ax
    jz .none
    add ax, 8
    call cs_hscalex
    mov cx, ax
    mov ax, 8
    call cs_hscalex
    cmp ax, cx
    jg .none
    mov al, CSI_PHI
    call cs_setink
    mov ax, 8
    call cs_hscalex
    mov bx, [cs_pany]
    add bx, CS_PR3
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
    mov dx, CS_PR4
    add dx, [cs_pany]
    call cs_text
    ret
cs_d_keys:
    mov al, CSI_PFG
    call cs_setink
    mov si, cs_s_keys
    mov ax, [cs_vw]
    sub ax, 320
    shr ax, 1
    mov cx, ax
    mov dx, CS_PR5
    add dx, [cs_pany]
    call cs_text
    ret

cs_s_spd:    db 'SPD ', 0
cs_s_alt:    db 'ALT ', 0
cs_s_hdg:    db 'HDG ', 0
cs_s_vs:     db 'VS ', 0
cs_s_thr:    db 'THR ', 0
cs_s_ground: db 'ON THE GROUND', 0
cs_s_flying: db 'FLYING       ', 0
cs_s_stalled: db 'STALL        ', 0
cs_s_crash:  db 'CRASHED      ', 0
cs_s_keys:   db 'ARROWS FLY W/S THR A/D RUD B BRAKE ESC F', 0

cs_msgtab:   dw cs_g_none, cs_g_takeoff, cs_g_stall, cs_g_landed
             dw cs_g_crash, cs_g_paused, cs_g_edge
cs_g_none:   db 0
cs_g_takeoff: db 'FULL THROTTLE, PULL BACK AT 55 KNOTS', 0
cs_g_stall:  db 'STALL - NOSE DOWN, POWER ON', 0
cs_g_landed: db 'LANDED', 0
cs_g_crash:  db 'CRASHED INTO ', 0
cs_g_paused: db 'PAUSED', 0
cs_g_edge:   db 'THE EDGE OF THE WORLD - TURN BACK', 0
