; =============================================================================
; os8088 - apps/tithe/tipj.inc
;
; THE PROJECTILES (SPEC.md 97.4.5, TITHE-PLAN 3.9.1) - the moving things on
; this board that are NOT self-erasing bands.
;
; Every other mover is an opaque band with its ground baked in, so drawing it
; where it was IS the erase. A projectile cannot be: an arrow crosses cells
; whose ground it does not own, so there is nothing to bake. It is COMPOSED
; every frame instead - the board as the glass shows it, ground AND figures
; (ti_pic_band), the bolts OR'd over it, the numbers over them, one commit -
; which is `dotdel`'s shape one game along (SPEC.md 93.5.1).
;
; TWO AT ONCE, AND THEY CROSS. The resolution plays a lane's melee, then its
; ranged, then its heals (TITHE-PLAN 6.5), so the worst the machine has to
; carry is ONE BOLT A SIDE in the same lane - P1's rear flying right and
; P2's flying left - and that is what `A` sustains. Each band ORs in EVERY
; bolt that lands in it, so where the two pass they both show.
; =============================================================================

TI_PJW      equ 32                ; the band, in pixels: the byte the bolt is in
                                  ; and the byte it was in a step ago, three on
TI_PJB      equ TI_PJW / 8
TI_PJHMAX   equ 26
TI_PJMAX    equ TI_PJB * TI_PJHMAX
TI_PJN      equ 2                 ; bolts in the air at once, one a side
TI_PJSTEP   equ 24                ; pixels a frame - A MULTIPLE OF 8, which is
                                  ; what keeps the ground copy a byte copy
                                  ; rather than a shifted read-modify-write.
                                  ; TITHE-PLAN 3.9.1 prices the masked version
                                  ; and it is 43% of the whole cost; a
                                  ; prototype that wants the SHAPE measured
                                  ; does not have to pay it

; -----------------------------------------------------------------------------
; ti_pj_lay - the projectile's band height, from the cell
; clobbers: AX
; -----------------------------------------------------------------------------
ti_pj_lay:
    push ax
    push dx
    ; THE BAND IS THE BOLT AND ONE STEP'S CLIMB EACH WAY, and no taller: its
    ; rows are the whole cost of composing it, and a bolt only ever needs the
    ; eight rows it is in and the ones it was in a step ago, which the lane's
    ; shear puts CLIMB rows above or below. Half a cell was 24 rows on a VGA
    ; where this is 20.
    mov ax, TI_PJSTEP
    mul word [ti_rise]
    div word [ti_cw]                ; AX = the climb a step
    shl ax, 1
    add ax, 8 + 2                   ; 8 rows of bolt, and a row each side
    mov dx, [ti_ch]
    shr dx, 1
    cmp ax, dx                      ; ...never taller than half a cell
    jbe .cell
    mov ax, dx
.cell:
    cmp ax, TI_PJHMAX
    jbe .cap
    mov ax, TI_PJHMAX
.cap:
    cmp ax, 8
    jae .have
    mov ax, 8
.have:
    mov [ti_pjh], ax
    pop dx
    pop ax
    ret

; -----------------------------------------------------------------------------
; ti_pj_fire - one bolt a side in lane [ti_pjlane]: P1's from column 0 going
; right, P2's from column 3 going left. Preserves every register.
; -----------------------------------------------------------------------------
ti_pj_fire:
    push ax
    push bx
    call ti_pj_lay
    mov al, 0                       ; P1's rear
    mov ah, [ti_pjlane]
    call ti_cellpos                 ; AX = x, BX = y
    add ax, [ti_insx]
    mov [ti_pjx], ax
    add bx, [ti_insy]
    mov [ti_pjy], bx
    mov al, TI_COLS - 1             ; ...and P2's
    mov ah, [ti_pjlane]
    call ti_cellpos
    add ax, [ti_insx2]
    mov [ti_pjx + 2], ax
    add bx, [ti_insy]
    mov [ti_pjy + 2], bx
    mov word [ti_pjon], 0101h
    pop bx
    pop ax
    ret

; ti_pj_live - AX = the bolts in the air, a band each. Preserves the rest.
ti_pj_live:
    xor ax, ax
    cmp byte [ti_pjon], 0
    je .one
    inc ax
.one:
    cmp byte [ti_pjon + 1], 0
    je .out
    inc ax
.out:
    ret

; -----------------------------------------------------------------------------
; ti_pj_frame - one frame of travel for every bolt: compose, commit, advance.
; AFTER THE WHEEL, so a band reads what the glass shows once this frame's idle
; commits are down, and a figure committed under a bolt cannot cut it.
; Preserves every register.
;
; A BOLT THAT ARRIVES spends one more frame on a band WITHOUT its own bolt at
; the last place it was drawn (state 2), which is its erase - it used to stop
; with its bolt still on the glass.
; -----------------------------------------------------------------------------
ti_pj_frame:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    push es
    push ds
    pop es
    cld
    call ti_pit                     ; WHAT IT REALLY COSTS, for the combat lane
    mov [ti_pjt0], ax               ; to charge (ti_pj_cost)
    xor bx, bx                      ; BX = the bolt
.band:
    cmp bx, TI_PJN
    jb .bgo
    jmp .adv
.bgo:
    cmp byte [ti_pjon + bx], 0
    jne .have
    jmp .bnext
.have:
    push bx
    mov ax, bx                      ; DI = its band
    mov cx, TI_PJMAX
    mul cx
    add ax, ti_pjband
    mov di, ax
    shl bx, 1
    mov ax, [ti_pjx + bx]
    mov [ti_pjbx], ax
    mov ax, [ti_pjy + bx]
    mov [ti_pjby], ax
    push di
    mov ax, [ti_pjbx]               ; --- the board as the glass shows it
    mov bx, [ti_pjby]
    mov cx, TI_PJB
    mov dx, [ti_pjh]
    call ti_pic_band
    pop di
    xor bx, bx                      ; --- EVERY bolt still flying that lands
.art:                               ;     in this band
    cmp bx, TI_PJN
    jae .arted
    cmp byte [ti_pjon + bx], 1
    jne .anext
    push bx
    shl bx, 1
    mov ax, [ti_pjx + bx]           ; its byte column in this band: at the
    sub ax, [ti_pjbx]               ; LEADING edge, so the band trails the
    mov cl, 3                       ; bolt and covers where it was - the last
    sar ax, cl                      ; byte going right, the first going left
    mov si, TI_PJB - 1
    or bx, bx
    jz .dirok
    xor si, si
.dirok:
    add ax, si
    mov si, ax
    mov ax, [ti_pjy + bx]           ; ...and its rows, the band's middle
    sub ax, [ti_pjby]
    mov dx, [ti_pjh]
    shr dx, 1
    sub dx, 4
    jns .mid
    xor dx, dx
.mid:
    add dx, ax                      ; DX = its first row in this band
    pop bx
    or si, si
    js .anext
    cmp si, TI_PJB
    jae .anext
    push bx
    push dx                         ; BP = its first byte: row x TI_PJB +
    mov ax, dx                      ; column, and a row further is TI_PJB on
    mov bp, TI_PJB                  ; - one signed multiply a bolt, and none
    imul bp                         ; a row
    pop dx
    mov bp, ax
    add bp, si
    mov bx, ti_pj_art
    mov cx, 8
.arow:
    or dx, dx
    js .askip
    cmp dx, [ti_pjh]
    jae .askip
    mov al, [bx]
    or [ds:di + bp], al
.askip:
    inc bx
    inc dx
    add bp, TI_PJB
    loop .arow
    pop bx
.anext:
    inc bx
    jmp short .art
.arted:
    mov ax, [ti_pjbx]               ; --- the NUMBERS over it all
    mov bx, [ti_pjby]
    call ti_pic_stat
    mov si, di                      ; --- and one commit
    mov ax, [ti_pjbx]
    mov bx, [ti_pjby]
    mov cx, TI_PJW
    mov dx, [ti_pjh]
    mov bp, TI_PJB
    call OSAPI_GFX_BLIT1
    pop bx
.bnext:
    inc bx
    jmp .band

.adv:                               ; --- and every bolt moves on
    xor bx, bx
.move:
    cmp bx, TI_PJN
    jae .out
    mov al, [ti_pjon + bx]
    cmp al, 2
    jne .fly
    mov byte [ti_pjon + bx], 0      ; its erase is down
    jmp short .mnext
.fly:
    cmp al, 1
    jne .mnext
    push bx
    mov ax, TI_PJSTEP               ; a lane climbs one RISE per cell, so a
    mul word [ti_rise]              ; step of TI_PJSTEP climbs its share
    div word [ti_cw]
    mov cx, ax                      ; CX = the climb
    mov si, bx
    shl si, 1
    or bx, bx
    jnz .left
    mov ax, [ti_pjx + si]           ; P1's, going right to the board's edge
    add ax, TI_PJSTEP
    mov dx, [ti_bx]
    add dx, [ti_boardw]
    sub dx, TI_PJW
    cmp ax, dx
    ja .end
    mov [ti_pjx + si], ax
    sub [ti_pjy + si], cx
    jmp short .moved
.left:
    mov ax, [ti_pjx + si]           ; P2's, going left to the board's edge
    mov dx, [ti_bx]
    add dx, TI_PJSTEP
    cmp ax, dx
    jb .end
    sub ax, TI_PJSTEP
    mov [ti_pjx + si], ax
    add [ti_pjy + si], cx
    jmp short .moved
.end:
    pop bx
    mov byte [ti_pjon + bx], 2      ; ...one more band, without it
    jmp short .mnext
.moved:
    pop bx
.mnext:
    inc bx
    jmp short .move
.out:
    call ti_pit                     ; counter 0 counts DOWN, 0.8381 us a count
    mov bx, [ti_pjt0]
    sub bx, ax
    mov ax, bx
    mov cx, 8381
    mul cx
    mov cx, 10000
    div cx
    mov [ti_pjus], ax
    pop es
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; ti_pj_cost - AX = what AX bolts cost the combat lane this frame: the model's
; price or what the last frame of them was TIMED at, whichever is more.
; Preserves every other register.
;
; THE MODEL UNDER-PRICES A COMPOSED BAND. It charges a blit's rows and
; arrival and as much again for the compose, and a band read from the board as
; the glass shows it - ground, figures, numbers - is two to three blits' worth
; on its own. Charged the model, two bolts over-ran the lane and took the frame
; with them: the idle fell 22% on a VGA while they flew. Charged the clock,
; the lane pays for its own bolts - and on a machine it cannot afford them
; every frame, it is the BOLTS that slow and not the board.
; -----------------------------------------------------------------------------
ti_pj_cost:
    push bx
    push cx
    push dx
    mov cx, ax
    mov ax, [ti_pjh]
    mul word [ti_rowus]
    add ax, [ti_arrus]
    shl ax, 1
    mul cx
    mov bx, [ti_pjus]               ; the timing is for the bolts it drew,
    cmp bx, ax                      ; which is this many again next frame
    jbe .have
    mov ax, bx
.have:
    pop dx
    pop cx
    pop bx
    ret
