; =============================================================================
; os8088 - apps/tithe/tipj.inc
;
; THE PROJECTILE (SPEC.md 97.4.5, TITHE-PLAN 3.9.1) - the one moving thing on
; this board that is NOT a self-erasing band.
;
; Every other mover is an opaque band with its ground baked in, so drawing it
; where it was IS the erase. A projectile cannot be: an arrow crosses cells
; whose ground it does not own, so there is nothing to bake. It is COMPOSED
; every frame instead - ground in, projectile OR'd over it, one commit - which
; is `dotdel`'s shape one game along (SPEC.md 93.5.1) and the most expensive
; thing in the renderer.
; =============================================================================

TI_PJW      equ 48                ; the band, in pixels
TI_PJB      equ TI_PJW / 8
TI_PJHMAX   equ 26
TI_PJMAX    equ TI_PJB * TI_PJHMAX
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
    mov ax, [ti_ch]
    shr ax, 1
    cmp ax, TI_PJHMAX
    jbe .cap
    mov ax, TI_PJHMAX
.cap:
    cmp ax, 8
    jae .have
    mov ax, 8
.have:
    mov [ti_pjh], ax
    pop ax
    ret

; -----------------------------------------------------------------------------
; ti_pj_fire - start one crossing lane [ti_pjlane], from P1's side
; Preserves every register.
; -----------------------------------------------------------------------------
ti_pj_fire:
    push ax
    push bx
    call ti_pj_lay
    mov al, 0                       ; column 0, the lane's own row
    mov ah, [ti_pjlane]
    call ti_cellpos                 ; AX = x, BX = y
    add ax, [ti_insx]
    mov [ti_pjx], ax
    add bx, [ti_insy]
    mov [ti_pjy], bx
    mov byte [ti_pjon], 1
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; ti_pj_step - one frame of travel: compose, commit, advance
; out: CF=1 it is still flying
; Preserves every register bar the flags.
;
; The four steps TITHE-PLAN 3.9.1 prices, in its order.
; -----------------------------------------------------------------------------
ti_pj_step:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    push es
    cmp byte [ti_pjon], 0
    je .stop

    ; --- 1 and 2: the GROUND the band lands on --------------------------
    ; The cells tile exactly (SPEC.md 97.3) and every cell's ground is the
    ; same diamond, so the ground under any point of the board is that one
    ; band read modulo the cell - which is why this is a byte copy and not a
    ; second picture in RAM. What it does not carry is a FIGURE the band laps;
    ; wave 3's board picture is where that comes from.
    push ds
    pop es
    cld
    mov ax, [ti_pjx]                ; the band's byte column inside a cell
    sub ax, [ti_bx]
    xor dx, dx
    div word [ti_cw]
    mov ax, dx                      ; DX = x mod CW
    shr ax, 1
    shr ax, 1
    shr ax, 1
    mov [ti_pjcx], ax

    mov ax, [ti_pjy]                ; ...and its row inside one
    sub ax, [ti_by]
    sub ax, [ti_lift]
    xor dx, dx
    div word [ti_ch]
    mov [ti_pjcy], dx

    mov ax, [ti_cw]
    shr ax, 1
    shr ax, 1
    shr ax, 1
    mov [ti_pjcs], ax               ; the cell's stride

    mov di, ti_pjband
    mov word [ti_pjr], 0
.row:
    mov ax, [ti_pjr]
    cmp ax, [ti_pjh]
    jae .done
    add ax, [ti_pjcy]
    xor dx, dx
    div word [ti_ch]
    mov ax, dx                      ; the cell row this band row reads
    mul word [ti_pjcs]
    mov si, ti_cell
    add si, ax
    mov cx, TI_PJB
    mov bx, [ti_pjcx]
.byte:
    push si
    add si, bx
    movsb
    pop si
    inc bx
    cmp bx, [ti_pjcs]
    jb .nw
    xor bx, bx                      ; ...wrapping at the cell, which is what
.nw:                                ; makes a tiling ground one band
    dec cx
    jnz .byte
    inc word [ti_pjr]
    jmp short .row
.done:

    ; --- 3: the projectile itself, OR'd over that ground ----------------
    mov ax, [ti_pjh]
    shr ax, 1
    sub ax, 4
    jns .mid
    xor ax, ax
.mid:
    mul word [ti_pjb]
    mov di, ti_pjband
    add di, ax
    add di, TI_PJB - 2              ; AT THE BAND'S LEADING EDGE, so the band
                                    ; TRAILS the bolt and covers where it was.
                                    ; Centred, a 24-pixel step puts the last
                                    ; frame's bolt 8 pixels LEFT of the new
                                    ; band and the thing leaves a track behind
                                    ; it - TITHE-PLAN 3.9.1's union(old, new)
                                    ; falls out of the geometry rather than
                                    ; needing a second rectangle
    mov si, ti_pj_art
    mov cx, 8
.orow:
    mov al, [si]
    or [di], al
    inc si
    add di, TI_PJB
    dec cx
    jnz .orow

    ; --- 4: one commit --------------------------------------------------
    push ds
    pop es
    mov si, ti_pjband
    mov ax, [ti_pjx]
    mov bx, [ti_pjy]
    mov cx, TI_PJW
    mov dx, [ti_pjh]
    mov bp, TI_PJB
    call OSAPI_GFX_BLIT1

    ; --- and the advance, along the lane's own shear --------------------
    mov ax, [ti_pjx]
    add ax, TI_PJSTEP
    mov [ti_pjx], ax
    mov bx, [ti_rise]               ; a lane climbs one RISE per cell, so a
    push ax                         ; step of TI_PJSTEP climbs its share
    mov ax, TI_PJSTEP
    mul bx
    div word [ti_cw]
    sub [ti_pjy], ax
    pop ax
    mov bx, [ti_bx]
    add bx, [ti_boardw]
    sub bx, TI_PJW
    cmp ax, bx
    jb .fly
.stop:
    mov byte [ti_pjon], 0
    pop es
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    clc
    ret
.fly:
    pop es
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    stc
    ret
