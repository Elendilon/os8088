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
TI_CLFRAMES equ 16                 ; how long a clash runs
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

    mov ax, [ti_insx2]              ; column 2: right half, at the top, and
    shr ax, 1                       ; P2's - so MIRRORED, facing its enemy
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
    mov byte [ti_fa_mir], 1
    call ti_cl_put
    mov byte [ti_fa_mir], 0

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

; ti_cl_put - the character's ATTACK frame for this moment of the clash,
; composed into the tier B band at [ti_clx] bytes and [ti_cly] rows - the
; figure and not the cell's band, which carries its own cell's ground and
; would lay a second ground over the first. Mirroring is the caller's.
; clobbers: AX, BX, CX, DX, SI, DI
ti_cl_put:
    mov ax, [ti_clbs]               ; the window: this cell's band inside the
    mov [ti_fa_stride], ax          ; two-cell one, so a mirrored figure turns
    mov ax, [ti_bs]                 ; about its own cell and not the pair
    mov [ti_fa_wb], ax
    mov ax, [ti_clh]
    mov [ti_fa_h], ax
    mov ax, [ti_bh]
    mov [ti_cbh], ax
    mov ax, [ti_cly]
    mov [ti_cdy], ax
    mov word [ti_cdx], 0
    mov ax, [ti_gidx]
    mov [ti_csurf], ax
    mov word [ti_cst], TI_ROW_FRONT ; the front line fights
    call ti_cl_frame
    call ti_cl_lunge                ; ...the step into the strike
    add ax, TI_POSES
    mov [ti_cfr], ax
    mov di, ti_clband
    add di, [ti_clx]
    call ti_char_put
    ret

; ti_cl_frame - AX = which of the four ATTACK frames the clash is on: the
; swing spread evenly over TI_CLFRAMES, so it lands in the middle of the lean.
; Preserves every other register.
ti_cl_frame:
    push dx
    mov al, TI_CLFRAMES
    sub al, [ti_clash]
    xor ah, ah
    shl ax, 1
    shl ax, 1                       ; x the four frames
    mov dl, TI_CLFRAMES
    div dl
    xor ah, ah
    cmp ax, TI_POSES - 1
    jbe .ok
    mov ax, TI_POSES - 1
.ok:
    pop dx
    ret

; ti_cl_lunge - [ti_cdx] = how far attack frame AX steps toward the enemy:
; TI_CLSTEP on the strike and the follow-through, nothing on the wind-up and
; the recovery. Preserves every register.
;
; THE LUNGE IS IN THE FRAME, NOT IN THE BAND. It moved the BAND eight pixels,
; which left the trailing eight columns of the last frame on the glass - on a
; mirrored P2 fighter, a slice of the figure standing beside it. Moving the
; character INSIDE its band keeps the band self-erasing (SPEC.md 97.4), and a
; mirrored cell mirrors the step with everything else, so P2 lunges left.
ti_cl_lunge:
    push ax
    mov word [ti_cdx], 0
    cmp ax, 1
    je .step
    cmp ax, 2
    jne .out
.step:
    mov word [ti_cdx], TI_CLSTEP / 8
.out:
    pop ax
    ret

; ti_cl_mine - CF=1 if cell AX is one of the two fighters in the clash now
; running (columns 1 and 2 of the lane). Preserves every register.
ti_cl_mine:
    push ax
    push cx
    push dx
    cmp byte [ti_clash], 0
    je .no
    xor dx, dx
    mov cx, TI_ROWS
    div cx                          ; AX = column, DX = row
    cmp dl, [ti_pjlane]
    jne .no
    cmp al, 1
    je .yes
    cmp al, 2
    je .yes
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

; ti_cl_tiera - TIER A's frame: both fighters, from their ATTACK slots, every
; frame of the clash - they lean and swing in their own rectangles, two
; ordinary bands and no composition (SPEC.md 97.4.7). Preserves registers.
ti_cl_tiera:
    push ax
    mov al, [ti_pjlane]
    xor ah, ah
    add ax, TI_ROWS                 ; cell (1, lane)
    call ti_feature
    add ax, TI_ROWS                 ; ...and (2, lane)
    call ti_feature
    pop ax
    ret
