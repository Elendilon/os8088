; =============================================================================
; os8088 - apps/tithe/ticl.inc
;
; THE MELEE CLASH, BOTH TIERS (SPEC.md 97.4.7, TITHE-PLAN 3.9.2).
;
; The reference lets its melee figures OVERLAP when they trade. This board's
; sheared grid gives every cell a rectangle of its own and the renderer blits
; one opaque band an actor, so overlapping is not something the default path
; can do. Two tiers, and the cheap one always works - which is why both are
; here to be LOOKED at rather than chosen by arithmetic.
; =============================================================================

TI_CLW      equ 2                  ; a tier B band spans TWO cells
TI_CLMAX    equ 26 * 80            ; ...at the widest cell and a band a whole
                                   ; RISE taller than one, which is what the
                                   ; shear makes a two-cell band
TI_CLFRAMES equ 12                 ; how long a clash runs
TI_CLSTEP   equ 8                  ; how far a fighter steps toward the line -
                                   ; A MULTIPLE OF 8, so tier A stays two
                                   ; ordinary bands with no composition at all

; -----------------------------------------------------------------------------
; ti_cl_fire - start a clash in lane [ti_pjlane], front columns 1 and 2
; Preserves every register.
; -----------------------------------------------------------------------------
ti_cl_fire:
    mov byte [ti_clash], TI_CLFRAMES
    ret

; -----------------------------------------------------------------------------
; ti_cl_lean - how far cell [ti_ci] steps toward the line this frame
; out: AX = the offset in pixels, signed
; Preserves every other register.
;
; TIER A, and the whole of it: the two front fighters lean toward the line,
; swing, and lean back, EACH IN ITS OWN RECTANGLE. Two bands a frame and no
; composition - which is why it always works, on every adapter and at every
; sprite size.
; -----------------------------------------------------------------------------
ti_cl_lean:
    push bx
    push cx
    push dx
    xor ax, ax
    cmp byte [ti_clash], 0
    je .out
    mov ax, [ti_ci]                 ; is this cell in the clashing lane's front
    mov cl, TI_ROWS                 ; line?
    xor dx, dx
    div cx                          ; AL = column, DL = row
    mov bl, dl
    cmp bl, [ti_pjlane]
    jne .none
    mov bl, al
    xor ax, ax
    cmp bl, 1
    je .p1
    cmp bl, 2
    je .p2
    jmp short .out
.p1:
    call ti_cl_phase                ; column 1 steps RIGHT, toward the line
    jmp short .out
.p2:
    call ti_cl_phase                ; ...and column 2 LEFT
    neg ax
    jmp short .out
.none:
    xor ax, ax
.out:
    pop dx
    pop cx
    pop bx
    ret

; ti_cl_phase - AX = TI_CLSTEP while the clash is in its middle third
; clobbers: AX, flags
ti_cl_phase:
    push bx
    xor ax, ax
    mov bl, [ti_clash]
    cmp bl, TI_CLFRAMES - TI_CLFRAMES / 3
    ja .out                         ; still leaning in
    cmp bl, TI_CLFRAMES / 3
    jb .out                         ; ...and leaning back
    mov ax, TI_CLSTEP
.out:
    pop bx
    ret

; -----------------------------------------------------------------------------
; ti_cl_tierb - TIER B: one band spanning both cells, both figures in it
; Preserves every register.
;
; An OPTION and a wave-3 decision, built here so the choice is made by looking.
; One band two cells wide, with both figures composed into it, so they may
; overlap freely - TITHE-PLAN 3.9.2 prices it at ~25 ms a frame live, which is
; affordable for ONE clash and not for five, and notes that pre-composing all
; five lanes in the reveal phase is 44 KB of heap.
;
; What it buys over tier A is that nothing is confined to a rectangle; what it
; costs is a band of 1,456 bytes against two of 392, composed rather than
; blitted.
; -----------------------------------------------------------------------------
ti_cl_tierb:
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

    ; --- THE BAND IS NOT A RECTANGLE IN BOARD SPACE, and that is the shear --
    ; Columns 1 and 2 are one RISE apart vertically (SPEC.md 97.3), so a band
    ; spanning both is a cell TALL PLUS A RISE, with each cell's content at its
    ; own offset inside it. A band cut to one cell's height composes the two
    ; figures at the same y and puts one of them a whole rise out of place -
    ; which on the glass is two fighters trading past each other.
    mov ax, [ti_cw]
    shr ax, 1
    shr ax, 1
    shr ax, 1
    mov [ti_clcs], ax               ; one cell's stride
    add ax, ax
    mov [ti_clbs], ax               ; ...and the band's, two cells wide
    mov ax, [ti_ch]
    add ax, [ti_rise]
    mov [ti_clh], ax
    mul word [ti_clbs]
    cmp ax, TI_CLMAX
    ja .out                         ; a surface whose two cells will not fit
    mov cx, ax                      ; the buffer simply keeps tier A
    mov di, ti_clband
    xor ax, ax
    rep stosb

    ; --- the GROUND, out of the two columns' strips (tiplace.inc) --------
    ; The band's top is column 1's cell top less a RISE, which is column 2's
    ; cell top - so a row of it is one screen row across both cells, and the
    ; ground reader hands back each half's own column, fences and all.
    mov al, 1
    mov ah, [ti_pjlane]
    call ti_cellpos                 ; AX = column 1's x, BX = its y
    sub bx, [ti_rise]
    mov cx, [ti_clbs]
    call ti_gnd_prep
    mov di, ti_clband
    mov dx, [ti_clh]
.grow:
    or dx, dx
    jz .gdone
    call ti_gnd_row
    add di, [ti_clbs]
    inc bx
    dec dx
    jmp short .grow
.gdone:

    ; --- both FIGURES, each at its own cell's offset -----------------------
    mov ax, [ti_insx]               ; column 1: left half, a rise down
    shr ax, 1
    shr ax, 1
    shr ax, 1
    mov [ti_clx], ax
    mov ax, [ti_insy]
    add ax, [ti_rise]
    mov [ti_cly], ax
    mov al, [ti_pjlane]             ; ...WHO stands there: the figure is the
    xor ah, ah                      ; character's own, cell (1, lane)
    add ax, TI_ROWS
    call ti_ck_cell
    call ti_cl_put

    mov ax, [ti_insx]               ; column 2: right half, at the top
    shr ax, 1
    shr ax, 1
    shr ax, 1
    add ax, [ti_clcs]
    mov [ti_clx], ax
    mov ax, [ti_insy]
    mov [ti_cly], ax
    mov al, [ti_pjlane]             ; ...and cell (2, lane)
    xor ah, ah
    add ax, 2 * TI_ROWS
    call ti_ck_cell
    call ti_cl_put

    ; --- and ONE commit, at the HIGHER cell's top --------------------------
    mov al, 1
    mov ah, [ti_pjlane]
    call ti_cellpos                 ; AX = column 1's x, BX = its y
    sub bx, [ti_rise]               ; ...which is a rise below column 2's
    mov si, ti_clband
    mov cx, [ti_cw]
    add cx, [ti_cw]
    mov dx, [ti_clh]
    mov bp, [ti_clbs]
    call OSAPI_GFX_BLIT1
    inc word [ti_ncl]
.out:
    pop es
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; ti_cl_put - the idle pose's FIGURE, masked into the tier B band at
; [ti_clx] bytes and [ti_cly] rows - the figure and not the pose's band, which
; carries its own cell's ground and would lay a second ground over the first
; clobbers: AX, BX, CX, DX, SI, DI
ti_cl_put:
    push si
    mov ax, [ti_gidx]
    call ti_crec_at
    mov al, [si + TI_CR_Y]          ; pose 0
    xor ah, ah
    add ax, [ti_cly]
    mov [ti_fa_dy], ax
    mov si, [si]
    mov ax, [ti_clx]
    mov [ti_fa_dx], ax
    mov ax, [ti_clbs]
    mov [ti_fa_stride], ax
    mov [ti_fa_wb], ax
    mov ax, [ti_clh]
    mov [ti_fa_h], ax
    mov byte [ti_fa_or], 0
    mov di, ti_clband
    call ti_fig_apply
    pop si
    ret
