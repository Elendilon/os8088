; =============================================================================
; os8088 - apps/skies/csflight.inc
;
; THE FLIGHT MODEL (SPEC.md 88.7). Deliberately simple, and stepped ONCE PER
; SYSTEM TICK the way TANK ATTACK steps its world (SPEC.md 85.6): the machine
; draws as fast as it can and the aeroplane flies at one speed on every
; machine. Speeds are 16.8 m/s, positions 16.8 metres in a dword, angles
; 65536 to the turn. Every constant is read out of [cs_plane]'s record.
; =============================================================================

; -----------------------------------------------------------------------------
; cs_runway_build - build the runway from [cs_airport] and put the aeroplane on it
; clobbers everything
; -----------------------------------------------------------------------------
cs_runway_build:
    mov si, [cs_airport]
    mov ax, [si + CSA_HDG]
    call cs_sin
    mov [cs_rwsin], ax
    mov ax, [si + CSA_HDG]
    call cs_cos
    mov [cs_rwcos], ax
    ; --- the four corners: +-hlen along, +-hwid across, turned by the heading
    ; along = (sin, cos), across = (cos, -sin)
    mov si, [cs_airport]
    mov ax, [si + CSA_HLEN]
    mov bx, [cs_rwsin]
    MUL14
    mov [cs_rwax], ax               ; along, x
    mov si, [cs_airport]
    mov ax, [si + CSA_HLEN]
    mov bx, [cs_rwcos]
    MUL14
    mov [cs_rwaz], ax               ; along, z
    mov si, [cs_airport]
    mov ax, [si + CSA_HWID]
    mov bx, [cs_rwcos]
    MUL14
    mov [cs_rwcx], ax               ; across, x
    mov si, [cs_airport]
    mov ax, [si + CSA_HWID]
    mov bx, [cs_rwsin]
    MUL14
    neg ax
    mov [cs_rwcz], ax               ; across, z
    mov di, cs_rwverts
    ; v0 = +along +across, v1 = -along +across, v2 = -along -across,
    ; v3 = +along -across; v4/v5 = the centreline's ends
    mov ax, [cs_rwax]
    add ax, [cs_rwcx]
    mov [di], ax
    mov ax, [cs_rwaz]
    add ax, [cs_rwcz]
    mov [di+2], ax
    mov ax, [cs_rwcx]
    sub ax, [cs_rwax]
    mov [di+4], ax
    mov ax, [cs_rwcz]
    sub ax, [cs_rwaz]
    mov [di+6], ax
    mov ax, [cs_rwax]
    add ax, [cs_rwcx]
    neg ax
    mov [di+8], ax
    mov ax, [cs_rwaz]
    add ax, [cs_rwcz]
    neg ax
    mov [di+10], ax
    mov ax, [cs_rwax]
    sub ax, [cs_rwcx]
    mov [di+12], ax
    mov ax, [cs_rwaz]
    sub ax, [cs_rwcz]
    mov [di+14], ax
    mov ax, [cs_rwax]
    mov [di+16], ax
    mov ax, [cs_rwaz]
    mov [di+18], ax
    neg ax
    mov [di+22], ax
    mov ax, [cs_rwax]
    neg ax
    mov [di+20], ax
    ; --- the model and the object, in bss ------------------------------------
    mov di, cs_rwmodel
    mov byte [di + CSM_TYPE], CSM_FLAT
    mov byte [di + CSM_NV], 6
    mov byte [di + CSM_NF], 1
    mov byte [di + CSM_NE], 4       ; the centreline is cs_rwline's (88.6.2)
    mov byte [di + CSM_EINK], CSI_MARK
    mov si, [cs_airport]
    mov ax, [si + CSA_HLEN]
    add ax, [si + CSA_HWID]
    mov [di + CSM_RAD], ax
    mov word [di + CSM_VERTS], cs_rwverts
    mov word [di + CSM_FACES], cs_f_rwy
    mov word [di + CSM_EDGES], cs_e_rwy
    mov ax, RW_DASHM                ; a stripe in Q15 of the centreline:
    mov dx, 16384                   ; RW_DASHM x 32768 / (2 hlen)
    mul dx
    div word [si + CSA_HLEN]
    mov [cs_rwdu], ax
    mov di, cs_rwobj
    mov word [di + CSO_MODEL], cs_rwmodel
    mov word [di + CSO_FAR], 0
    mov ax, [si + CSA_X]
    mov [di + CSO_X], ax
    mov ax, [si + CSA_Z]
    mov [di + CSO_Z], ax
    mov ax, [si + CSA_ELEV]
    mov [di + CSO_Y], ax
    mov word [di + CSO_RANGE], 16000
    mov word [di + CSO_LOD], 0
    mov ax, [si + CSA_NAME]
    mov [di + CSO_NAME], ax
    mov word [di + CSO_FLAGS], 0
    ret

; -----------------------------------------------------------------------------
; cs_reset - the aeroplane back at the airport's reset point, engine off
; clobbers everything
; -----------------------------------------------------------------------------
cs_reset:
    call cs_skipclr                 ; every object is a stranger again
    mov si, [cs_airport]
    mov ax, [si + CSA_SPAWN]
    mov bx, [cs_rwsin]
    MUL14
    add ax, [si + CSA_X]
    cwd
    mov cl, 8                       ; to 16.8
    call cs_shl32
    mov [cs_px], ax
    mov [cs_px+2], dx
    mov si, [cs_airport]
    mov ax, [si + CSA_SPAWN]
    mov bx, [cs_rwcos]
    MUL14
    add ax, [si + CSA_Z]
    cwd
    call cs_shl32
    mov [cs_pz], ax
    mov [cs_pz+2], dx
    mov si, [cs_airport]
    mov ax, [si + CSA_ELEV]
    cwd
    call cs_shl32
    mov [cs_py], ax
    mov [cs_py+2], dx
    mov ax, [si + CSA_HDG]
    mov [cs_hdg], ax
    xor ax, ax
    mov [cs_pitch], ax
    mov [cs_roll], ax
    mov [cs_spd], ax
    mov [cs_vs], ax
    mov [cs_thr], ax
    mov [cs_thrust], ax
    mov [cs_crasht], ax
    mov byte [cs_state], CS_ST_GROUND
    mov byte [cs_stall], 0
    mov byte [cs_msg], CSG_TAKEOFF
    mov byte [cs_inited], 1
    ret

; cs_shl32 - DX:AX <<= 8. Clobbers CX.
cs_shl32:
    mov cx, 8
.s:
    shl ax, 1
    rcl dx, 1
    loop .s
    ret

; -----------------------------------------------------------------------------
; cs_step - one tick of the world (SPEC.md 88.7)
; clobbers everything
; -----------------------------------------------------------------------------
cs_step:
    cmp byte [cs_state], CS_ST_CRASH
    jne .live
    dec word [cs_crasht]            ; the picture stays for CS_CRASHT ticks,
    jnz .out                        ; then the runway again
    call cs_reset
.out:
    ret
.live:
    mov di, [cs_plane]
    ; --- the throttle -------------------------------------------------------
    mov al, [cs_kthr]
    or al, al
    jz .throk
    cbw
    shl ax, 1
    add ax, [cs_thr]
    jns .t0
    xor ax, ax
.t0:
    cmp ax, 100
    jle .t1
    mov ax, 100
.t1:
    mov [cs_thr], ax
    mul word [di + CSP_THRUST]      ; thrust = THRUST x thr / 100
    mov bx, 100
    div bx
    mov [cs_thrust], ax
.throk:
    ; --- the speed: thrust, less drag, less gravity along the nose ---------
    mov ax, [cs_spd]
    mul ax                          ; DX:AX = v^2 (16.16)
    mov ax, dx                      ; AX = v^2 in whole m^2/s^2
    mul word [di + CSP_DRAGK]
    mov bx, dx                      ; BX = the drag, a tick
    mov ax, [cs_thrust]
    sub ax, bx
    mov cx, ax                      ; CX = thrust - drag
    cmp byte [cs_state], CS_ST_GROUND
    jne .air
    jmp .ground
.air:
    mov ax, [cs_pitch]
    push cx
    push di
    call cs_sin
    pop di
    pop cx
    mov bx, CS_GRAV
    MUL14
    sub cx, ax                      ; less g sin(pitch)
    mov ax, [cs_spd]
    add ax, cx
    jns .s0
    xor ax, ax
.s0:
    mov bx, [di + CSP_VMAX]
    mov cx, bx
    shr cx, 1
    shr cx, 1
    add bx, cx                      ; ...and a dive tops out at 1.25 VMAX
    cmp ax, bx
    jle .s1
    mov ax, bx
.s1:
    mov [cs_spd], ax
    ; --- attitude: the held keys, and the return to level -------------------
    mov al, [cs_kroll]
    cbw
    mov bx, [di + CSP_ROLLR]
    mov cx, [di + CSP_ROLLL]
    mov dx, [di + CSP_MAXROLL]
    mov si, cs_roll
    call cs_axis
    mov al, [cs_kpitch]
    cbw
    mov bx, [di + CSP_PITCHR]
    mov cx, [di + CSP_PITCHT]
    mov dx, [di + CSP_MAXPITCH]
    mov si, cs_pitch
    call cs_axis
    ; --- the stall: below VSTALL the nose drops and the wing stops lifting ---
    mov byte [cs_stall], 0
    mov ax, [cs_spd]
    cmp ax, [di + CSP_VSTALL]
    jae .nostall
    mov byte [cs_stall], 1
    mov byte [cs_msg], CSG_STALL
    mov ax, [cs_pitch]
    sub ax, CS_STALLDROP
    mov bx, [di + CSP_MAXPITCH]
    neg bx
    cmp ax, bx
    jge .sd
    mov ax, bx
.sd:
    mov [cs_pitch], ax
.nostall:
    cmp byte [cs_stall], 0          ; ...and the warning goes when it ends
    jne .warned
    cmp byte [cs_msg], CSG_STALL
    jne .warned
    mov byte [cs_msg], CSG_NONE
.warned:
    ; --- the turn: TURNK sin(roll) a tick, and the rudder ------------------
    mov ax, [cs_roll]
    push di
    call cs_sin
    pop di
    mov bx, [di + CSP_TURNK]
    MUL14
    add [cs_hdg], ax
    mov al, [cs_kyaw]
    cbw
    mov bx, CS_RUDDER
    imul bx
    add [cs_hdg], ax
    ; --- the motion: where the nose points, at the speed -------------------
    mov ax, [cs_pitch]
    push di
    call cs_cos
    pop di
    mov bx, [cs_spd]
    MUL14
    mov [cs_hs], ax                 ; the horizontal component
    mov ax, [cs_pitch]
    push di
    call cs_sin
    pop di
    mov bx, [cs_spd]
    MUL14                           ; ...and the vertical
    cmp byte [cs_stall], 0
    je .vsok
    mov bx, [di + CSP_VSTALL]
    sub bx, [cs_spd]                ; the deficit, and half of it is sink
    sar bx, 1
    sub ax, bx
.vsok:
    mov [cs_vs], ax
    call cs_move
    ; --- the ground, and what is standing on it ---------------------------
    ; The wheels are on it when the altitude is BELOW the field, or AT it
    ; (to the metre) and not climbing: a lift-off's first tick is centimetres
    ; up and the whole-metre compare alone put it straight back down.
    mov si, [cs_airport]
    mov ax, [si + CSA_ELEV]
    mov bx, [cs_py+1]               ; the altitude's whole metres
    cmp bx, ax
    jg .aloft
    jl .touch
    cmp word [cs_vs], 0
    jg .aloft
.touch:
    call cs_touch
    jmp short .done
.aloft:
    cmp bx, CS_CEIL
    jle .c1
    mov word [cs_py+1], CS_CEIL     ; the ceiling that keeps a word a word
    mov byte [cs_py], 0
.c1:
    call cs_collide
.done:
    call cs_fence
    ret

    ; ===== on the ground ====================================================
.ground:
    sub cx, [di + CSP_FRICT]        ; rolling friction, and the brakes
    cmp byte [cs_kbrake], 0
    je .g0
    sub cx, [di + CSP_BRAKE]
.g0:
    mov ax, [cs_spd]
    add ax, cx
    jns .g1
    xor ax, ax
.g1:
    mov [cs_spd], ax
    mov word [cs_roll], 0
    mov byte [cs_stall], 0
    ; the nose: only above VROT, and only when pulled
    mov bx, [cs_pitch]
    cmp ax, [di + CSP_VROT]
    jb .nodown
    cmp byte [cs_kpitch], 0
    jle .nodown
    add bx, [di + CSP_PITCHR]
    cmp bx, 2730                    ; 15 degrees on the wheels
    jle .np
    mov bx, 2730
.np:
    mov [cs_pitch], bx
    cmp bx, CS_LIFTOFF
    jl .steer
    mov byte [cs_state], CS_ST_AIR  ; and it flies
    mov byte [cs_msg], CSG_NONE
    jmp short .steer
.nodown:
    sub bx, [di + CSP_PITCHR]
    jns .nd1
    xor bx, bx
.nd1:
    mov [cs_pitch], bx
.steer:
    mov al, [cs_kyaw]               ; the nosewheel: hdg += v x STEERK >> 8
    cbw
    mov bx, [cs_spd]
    mov cl, 8
    shr bx, cl
    shl bx, 1                       ; CS_STEERK = 2
    imul bx
    add [cs_hdg], ax
    mov ax, [cs_spd]
    mov [cs_hs], ax
    mov word [cs_vs], 0
    call cs_move
    mov si, [cs_airport]            ; the wheels stay on the ground
    mov ax, [si + CSA_ELEV]
    mov [cs_py+1], ax
    mov byte [cs_py], 0
    call cs_fence
    ret

; cs_axis - one control axis: AX = the key (-1/0/1), BX = the held rate,
; CX = the return rate, DX = the limit, SI = the angle word. Clobbers AX, BX.
cs_axis:
    or ax, ax
    jz .ret
    push dx                         ; imul writes DX, and DX is the limit
    imul bx
    pop dx
    add ax, [si]
    cmp ax, dx
    jle .lo
    mov ax, dx
.lo:
    neg dx
    cmp ax, dx
    jge .st
    mov ax, dx
.st:
    mov [si], ax
    ret
.ret:
    mov ax, [si]                    ; nothing held: toward zero by CX
    or ax, ax
    jz .done
    js .neg
    sub ax, cx
    jns .st
    xor ax, ax
    jmp short .st
.neg:
    add ax, cx
    js .st
    xor ax, ax
    jmp short .st
.done:
    ret

; cs_move - one tick of [cs_hs] along [cs_hdg] and [cs_vs] up. The per-tick
; displacement is v / 18.2, which is v x 3600 >> 16.
cs_move:
    mov ax, [cs_hs]
    mov bx, 3600
    imul bx
    mov ax, dx                      ; AX = metres a tick, 16.8
    mov [cs_ht], ax
    mov ax, [cs_hdg]
    call cs_sin
    mov bx, [cs_ht]
    MUL14
    cwd
    add [cs_px], ax
    adc [cs_px+2], dx
    mov ax, [cs_hdg]
    call cs_cos
    mov bx, [cs_ht]
    MUL14
    cwd
    add [cs_pz], ax
    adc [cs_pz+2], dx
    mov ax, [cs_vs]
    mov bx, 3600
    imul bx
    mov ax, dx
    cwd
    add [cs_py], ax
    adc [cs_py+2], dx
    ret

; cs_fence - the world is +-CS_EDGE metres, and the aeroplane stays in it
cs_fence:
    mov si, cs_px
    call .one
    mov si, cs_pz
    call .one
    ret
.one:
    mov ax, [si+1]
    cmp ax, CS_EDGE
    jg .hi
    cmp ax, -CS_EDGE
    jl .lo
    ret
.hi:
    mov word [si+1], CS_EDGE
    mov byte [si], 0
    mov byte [cs_msg], CSG_EDGE
    ret
.lo:
    mov word [si+1], -CS_EDGE
    mov byte [si], 0
    mov byte [cs_msg], CSG_EDGE
    ret

; -----------------------------------------------------------------------------
; cs_touch - the wheels met the ground: a landing, or not (SPEC.md 88.7)
; -----------------------------------------------------------------------------
cs_touch:
    call cs_runway_xy               ; [cs_along]/[cs_across]
    mov si, [cs_airport]
    mov ax, [cs_along]
    or ax, ax
    jns .a1
    neg ax
.a1:
    cmp ax, [si + CSA_HLEN]
    jg .crash
    mov ax, [cs_across]
    or ax, ax
    jns .a2
    neg ax
.a2:
    cmp ax, [si + CSA_HWID]
    jg .crash
    cmp word [cs_vs], CS_LANDVS
    jl .crash
    mov ax, [cs_roll]
    or ax, ax
    jns .a3
    neg ax
.a3:
    cmp ax, CS_LANDROLL
    jg .crash
    mov ax, [cs_pitch]
    cmp ax, CS_LANDPMIN
    jl .crash
    cmp ax, CS_LANDPMAX
    jg .crash
    ; --- down, and rolling --------------------------------------------------
    mov byte [cs_state], CS_ST_GROUND
    mov ax, [si + CSA_ELEV]
    mov [cs_py+1], ax
    mov byte [cs_py], 0
    mov word [cs_pitch], 0
    mov word [cs_roll], 0
    mov word [cs_vs], 0
    mov byte [cs_msg], CSG_LANDED
    inc word [cs_landings]
    ret
.crash:
    mov si, cs_n_ground
    jmp cs_crash

; cs_runway_xy - the aeroplane in the runway's coordinates: along its heading
; and across it, whole metres
cs_runway_xy:
    mov si, [cs_airport]
    mov ax, [cs_px+1]
    sub ax, [si + CSA_X]
    mov [cs_ddx], ax
    mov ax, [cs_pz+1]
    sub ax, [si + CSA_Z]
    mov [cs_ddz], ax
    mov ax, [cs_ddx]
    mov bx, [cs_rwsin]
    MUL14
    mov cx, ax
    mov ax, [cs_ddz]
    mov bx, [cs_rwcos]
    MUL14
    add ax, cx
    mov [cs_along], ax
    mov ax, [cs_ddx]
    mov bx, [cs_rwcos]
    MUL14
    mov cx, ax
    mov ax, [cs_ddz]
    mov bx, [cs_rwsin]
    MUL14
    sub cx, ax
    mov [cs_across], cx
    ret

; -----------------------------------------------------------------------------
; cs_collide - the aeroplane against every CSO_COLLIDE box (SPEC.md 88.6)
; -----------------------------------------------------------------------------
cs_collide:
    mov si, cs_objtab
    mov cx, CS_NOBJ
.o:
    test word [si + CSO_FLAGS], CSO_COLLIDE
    jz .next
    mov ax, [cs_px+1]
    sub ax, [si + CSO_X]
    jns .x1
    neg ax
.x1:
    mov bx, [si + CSO_MODEL]
    mov di, [bx + CSM_VERTS]        ; level 0: wx, h, wz
    cmp ax, [di]
    jge .next
    mov ax, [cs_pz+1]
    sub ax, [si + CSO_Z]
    jns .z1
    neg ax
.z1:
    cmp ax, [di+4]
    jge .next
    mov al, [bx + CSM_NV]           ; the tallest level is the last
    xor ah, ah
    dec ax
    mov dx, ax
    shl ax, 1
    add ax, dx
    shl ax, 1                       ; x 6
    add di, ax
    mov ax, [di+2]
    add ax, [si + CSO_Y]
    cmp [cs_py+1], ax
    jge .next
    mov si, [si + CSO_NAME]
    jmp cs_crash
.next:
    add si, CSO_SIZE
    loop .o
    ret

; -----------------------------------------------------------------------------
; cs_crash - SI = what was hit. The picture freezes with the reason on the
;            panel for CS_CRASHT ticks, then cs_reset (SPEC.md 88.7)
; -----------------------------------------------------------------------------
cs_crash:
    mov [cs_crashwhy], si
    mov byte [cs_state], CS_ST_CRASH
    mov word [cs_crasht], CS_CRASHT
    mov byte [cs_msg], CSG_CRASH
    inc word [cs_crashes]
    cmp byte [cs_sound], 0
    je .quiet
    mov ax, 110                     ; a low blast, a second long
    mov cx, 18
    mov dl, 0x40
    call OSAPI_SND_TONE
    mov word [cs_tone], 0xFFFF      ; ...and the engine tone is re-issued
                                    ; after it, whatever it was
.quiet:
    ret

; -----------------------------------------------------------------------------
; cs_sound_step - the engine tone follows the throttle; a stall beeps
;                 (SPEC.md 88.8). Once a tick.
; -----------------------------------------------------------------------------
cs_sound_step:
    xor ax, ax                      ; AX = the tone wanted
    cmp byte [cs_sound], 0
    je .want
    cmp byte [cs_state], CS_ST_CRASH
    je .want
    mov ax, [cs_thr]
    or ax, ax
    jz .st
    add ax, 50
.st:
    cmp byte [cs_stall], 0
    je .want
    inc byte [cs_stallt]
    cmp byte [cs_stallt], 9
    jb .sb
    mov byte [cs_stallt], 0
.sb:
    cmp byte [cs_stallt], 4
    jae .want
    mov ax, 900                     ; the stall warning: four ticks in nine
.want:
    cmp ax, [cs_tone]
    je .out
    mov [cs_tone], ax
    xor cx, cx
    mov dl, 0x40
    call OSAPI_SND_TONE
.out:
    ret
