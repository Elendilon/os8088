; =============================================================================
; os8088 - apps/tithe/tirend.inc
;
; THE RENDERER (SPEC.md 97.4, 97.5). One rule and one loop.
;
; THE RULE: a feature is put down as ONE OPAQUE BAND THAT INCLUDES ITS OWN
; GROUND, so drawing it where it was IS the erase. There is no instant at
; which a sprite is off the glass and there is no erase pass at all. That is
; SPEC.md 79.5.1's finding and 93.5.1's, and this package does not get to
; relearn it - the screen saver's first draft blanked the box and then drew
; into it, and the field called it "the fish flicker".
;
; THE LOOP: SPEC.md 97.5's pacing wheel. A credit in MICROSECONDS a frame,
; walked from where it stopped, remembering the position. Not bytes: a band
; costs `arrival + rows x R + bytes x B` (SPEC.md 5.4.2.6), so a wide short
; band and a narrow tall one of the same size differ by 2x, and a byte credit
; would over-spend on the tall ones - which is the "some characters animate
; smoothly while others hitch" failure the wheel exists to remove.
;
; WAVE 1a's ART IS PROCEDURAL AND SAYS SO. `ti_pose_build` draws a figure out
; of arithmetic rather than reading one off the disk, because what wave 1a is
; for is the LAYOUT and the RATE - whether twenty figures at this size on this
; grid read as a crowd, and whether the wheel holds 18 fps while they do.
; docs/plans/TITHE-PLAN.md 16.1 is the checklist and the concept art is the
; owner's; nothing here assumes what it will look like beyond its box.
; =============================================================================

TI_POSES    equ 4                 ; a ping-pong idle: A B C B (SPEC.md 97.5)
TI_BANDMAX  equ 8 * 56            ; the largest band any surface asks for -
                                  ; 64x40 is 320 and 56x56 is 392, so eight
                                  ; bytes a row by fifty-six rows covers every
                                  ; row of SPEC.md 97.2's table with slack
TI_CELLMAX  equ 15 * 72           ; ...and the largest CELL ground, 120x52 and
                                  ; 104x72 both inside fifteen bytes by
                                  ; seventy-two rows

; -----------------------------------------------------------------------------
; ti_art_build - compose the cell ground and the four idle poses, once
; in:  the layout is current
; out: ti_cell and ti_pose[0..3] filled. Preserves every register.
;
; COMPOSED AT A SIZE CHANGE AND NEVER INSIDE A FRAME (SPEC.md 97.2). What the
; renderer blits is a finished opaque band, exactly as if it had been drawn
; that way - which is what lets the frame be one call a feature.
; -----------------------------------------------------------------------------
ti_art_build:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    push ds
    pop es
    cld

    ; --- the cell's ground: a baked isometric diamond -----------------------
    ; One band, blitted at all twenty cells. The pitch is a whole number of
    ; cells by construction (SPEC.md 97.3), so every cell's ground is the
    ; IDENTICAL diamond - if it varied per cell a sprite frame would need one
    ; baked variant per cell and the art would multiply by twenty.
    mov di, ti_cell
    mov cx, TI_CELLMAX
    xor ax, ax
    rep stosb                       ; dark ground: a set bit is LIT (5.4.2)

    mov word [ti_ry], 0
.crow:
    mov ax, [ti_ry]
    cmp ax, [ti_ch]
    jae .cdone
    ; the diamond's half-width at this row: |row - ch/2| scaled to cw/2
    mov bx, [ti_ch]
    shr bx, 1
    sub ax, bx                      ; AX = row - ch/2, signed
    jns .cpos
    neg ax
.cpos:
    mov dx, [ti_cw]
    shr dx, 1
    push dx
    mul dx                          ; |dy| * (cw/2)
    pop cx
    push bx
    or bx, bx
    jnz .cdiv
    inc bx
.cdiv:
    div bx                          ; ...over ch/2
    pop bx
    mov cx, [ti_cw]
    shr cx, 1
    sub cx, ax                      ; CX = the half-width at this row
    jbe .cnext
    call ti_cell_span
.cnext:
    inc word [ti_ry]
    jmp short .crow
.cdone:

    ; --- the four poses -----------------------------------------------------
    mov word [ti_pi], 0
.pose:
    mov ax, [ti_pi]
    cmp ax, TI_POSES
    jae .pdone
    call ti_pose_build
    inc word [ti_pi]
    jmp short .pose
.pdone:
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; ti_cell_span - set CX pixels either side of the cell's centre on row [ti_ry]
; in:  CX = half-width, [ti_ry]
; clobbers: AX, BX, DX, SI, DI
; -----------------------------------------------------------------------------
ti_cell_span:
    push cx
    mov ax, [ti_cw]                 ; the row's first byte in the band
    shr ax, 1
    shr ax, 1
    shr ax, 1
    mov bx, ax                      ; BX = bytes a row
    mov ax, [ti_ry]
    mul bx
    mov di, ti_cell
    add di, ax                      ; DI = this row
    mov ax, [ti_cw]
    shr ax, 1
    mov dx, ax
    sub dx, cx                      ; DX = the first lit pixel
    add cx, cx                      ; CX = how many
.px:
    or cx, cx
    jz .out
    mov ax, dx
    mov bx, ax
    shr bx, 1
    shr bx, 1
    shr bx, 1                       ; BX = the byte
    and ax, 7
    push cx
    mov cl, al
    mov al, 80h
    shr al, cl                      ; AL = the bit, 7 leftmost (SPEC.md 5.4.2)
    pop cx
    or [di + bx], al
    inc dx
    dec cx
    jmp short .px
.out:
    pop cx
    ret

; -----------------------------------------------------------------------------
; ti_pose_build - one idle pose into ti_pose[ti_pi]
; in:  [ti_pi] = 0..3, the layout is current
; clobbers: AX, BX, CX, DX, SI, DI
;
; PROCEDURAL, AND THE SHAPE IS NOT THE POINT - a head, a body that leans by
; the pose, and the cell's own ground baked in underneath so the band is
; self-erasing (SPEC.md 97.4). What IS the point is that the four differ, so
; that an idle at the measured rate can be LOOKED at.
; -----------------------------------------------------------------------------
ti_pose_build:
    push es
    push ds
    pop es
    cld
    call ti_pose_addr               ; DI = this pose's band
    push di
    mov cx, TI_BANDMAX
    xor ax, ax
    rep stosb
    pop di

    ; the ground the figure stands on, so drawing it back IS the erase
    mov word [ti_ry], 0
.row:
    mov ax, [ti_ry]
    cmp ax, [ti_bh]
    jae .done
    call ti_pose_row
    inc word [ti_ry]
    jmp short .row
.done:
    pop es
    ret

; ti_pose_row - one row of the figure. [ti_ry] = the row, [ti_pi] = the pose.
ti_pose_row:
    push ax
    push bx
    push cx
    push dx
    push di

    call ti_pose_addr
    mov ax, [ti_bs]
    push dx
    mov dx, [ti_ry]
    push ax
    mov ax, dx
    pop dx
    mul dx                          ; AX = row * stride
    pop dx
    add di, ax                      ; DI = this row of this pose

    ; --- the figure's half-width at this row --------------------------------
    ; head for the top fifth, shoulders, then a body that tapers, and a LEAN
    ; that is the pose: poses 1 and 3 lean one way, 2 the other, 0 upright.
    mov ax, [ti_ry]
    mov bx, [ti_bh]
    mov cx, bx
    shr cx, 1
    shr cx, 1
    shr cx, 1                       ; CX = bh/8: the head's depth
    cmp ax, cx
    jae .body
    mov dx, cx                      ; the head: a small constant width
    shr dx, 1
    inc dx
    jmp short .have
.body:
    mov dx, [ti_bw]                 ; the body: widest at the shoulders and
    shr dx, 1                       ; tapering to the feet
    shr dx, 1
    push dx
    mov ax, [ti_ry]
    mul dx
    or bx, bx
    jnz .bdiv
    inc bx
.bdiv:
    div bx
    pop dx
    shr ax, 1
    sub dx, ax
    inc dx
.have:
    or dx, dx
    jz .out
    mov cx, dx                      ; CX = the half width

    ; --- the lean: the pose moves the figure's centre by a pixel or two -----
    mov ax, [ti_bw]
    shr ax, 1                       ; AX = the band's centre
    mov bx, [ti_pi]
    cmp bx, 1
    jne .l2
    inc ax
    jmp short .emit
.l2:
    cmp bx, 2
    jne .l3
    dec ax
    jmp short .emit
.l3:
    cmp bx, 3
    jne .emit
    inc ax
    inc ax
.emit:
    call ti_pose_span
.out:
    pop di
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; ti_pose_span - DI = the row, AX = centre, CX = half width
ti_pose_span:
    push ax
    push bx
    push cx
    push dx
    mov dx, ax
    sub dx, cx
    jns .ok
    xor dx, dx
.ok:
    add cx, cx
.px:
    or cx, cx
    jz .out
    cmp dx, [ti_bw]
    jae .out
    mov ax, dx
    mov bx, ax
    shr bx, 1
    shr bx, 1
    shr bx, 1
    and ax, 7
    push cx
    mov cl, al
    mov al, 80h
    shr al, cl
    pop cx
    or [di + bx], al
    inc dx
    dec cx
    jmp short .px
.out:
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; ti_pose_addr - DI = the band of pose [ti_pi]
ti_pose_addr:
    push ax
    push dx
    mov ax, [ti_pi]
    mov dx, TI_BANDMAX
    mul dx
    mov di, ti_pose
    add di, ax
    pop dx
    pop ax
    ret

; -----------------------------------------------------------------------------
; ti_board - the board, once: twenty cell grounds on the sheared grid
; in:  the gfx lock is held, the layout is current
; Preserves every register.
;
; TWENTY BLITS OF ONE BAND. The grid's pitch is a whole number of cells, so
; every cell's ground is the identical diamond (SPEC.md 97.3) - which is the
; whole reason the ground can be baked into a sprite's band at all.
; -----------------------------------------------------------------------------
; -----------------------------------------------------------------------------
; ti_ground - the content OUTSIDE the board: the HUD strip, the card panel and
; the bottom margin
; Preserves every register.
;
; WF_OWNBG IS A PROMISE AND THIS IS THE REST OF IT. The flag tells the kernel
; not to fill our content white before W_PAINT, which is what stops a whole
; board of flash before the first frame - and it means EVERY pixel of the
; content is ours. Painting only the board left the other three strips holding
; whatever window used to be there, which is what a Disk window overlapping
; this one showed through as. Three fills, once a paint, and none of them
; touches a pixel the board is about to draw (PERFORMANCE.md rule 2).
; -----------------------------------------------------------------------------
ti_ground:
    push ax
    push bx
    push cx
    push dx
    mov al, CBLACK
    call OSAPI_SET_COLOR

    mov ax, [ti_ox]                 ; 1. the HUD band, full width, above the
    mov bx, [ti_oy]                 ;    board
    mov cx, ax
    add cx, [ti_cw_box]
    dec cx
    mov dx, [ti_by]
    dec dx
    cmp dx, bx
    jb .right
    call OSAPI_GFX_FILL

.right:
    mov ax, [ti_bx]                 ; 2. the card panel, beside the board
    add ax, [ti_boardw]
    mov bx, [ti_by]
    mov cx, [ti_ox]
    add cx, [ti_cw_box]
    dec cx
    mov dx, bx
    add dx, [ti_boardh]
    dec dx
    cmp cx, ax
    jb .bot
    call OSAPI_GFX_FILL

.bot:
    mov ax, [ti_ox]                 ; 3. what is left under the board
    mov bx, [ti_by]
    add bx, [ti_boardh]
    mov cx, ax
    add cx, [ti_cw_box]
    dec cx
    mov dx, [ti_oy]
    add dx, [ti_ch_box]
    dec dx
    cmp dx, bx
    jb .out
    call OSAPI_GFX_FILL
.out:
    pop dx
    pop cx
    pop bx
    pop ax
    ret

ti_board:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    push es

    mov al, CBLACK                  ; the board's own ground, under the cells
    call OSAPI_SET_COLOR
    mov ax, [ti_bx]
    mov bx, [ti_by]
    mov cx, ax
    add cx, [ti_boardw]
    dec cx
    mov dx, bx
    add dx, [ti_boardh]
    dec dx
    call OSAPI_GFX_FILL

    push ds
    pop es
    mov word [ti_ci], 0
.cell:
    mov ax, [ti_ci]
    cmp ax, TI_CELLS
    jae .done
    call ti_cell_xy                 ; AX = x, BX = y for cell [ti_ci]
    mov si, ti_cell
    mov cx, [ti_cw]
    mov dx, [ti_ch]
    mov bp, [ti_cw]
    shr bp, 1
    shr bp, 1
    shr bp, 1
    call OSAPI_GFX_BLIT1            ; CF is the caller's to read; a refused
                                    ; cell is a cell that is not drawn, and
                                    ; the board is redrawn whole on the next
                                    ; paint rather than patched
    inc word [ti_ci]
    jmp short .cell
.done:
    pop es
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; ti_cell_xy - AX = x, BX = y of cell index [ti_ci], in column-major order
ti_cell_xy:
    push cx
    push dx
    mov ax, [ti_ci]
    xor dx, dx
    mov cx, TI_ROWS
    div cx                          ; AL = column, DL = row
    mov ah, dl
    call ti_cellpos
    pop dx
    pop cx
    ret
