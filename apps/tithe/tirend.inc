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
TI_BASEPOSES equ 8                ; A BASE GETS FOUR TIMES THE FRAMES, and the
                                  ; reason is the ART BUDGET rather than the
                                  ; renderer: the game has three bases against
                                  ; twenty characters, so a frame of base is
                                  ; drawn once where a frame of character is
                                  ; drawn twenty times. It was 2 - enough to
                                  ; read as alive - and the field asked for
                                  ; smoother once the rate question was
                                  ; settled. Eight frames at the base lane's
                                  ; 9.1 Hz is a cycle under a second where the
                                  ; figures' four at 3.5 is over one.
                                  ; POWER OF TWO: ti_base_addr masks
TI_BASEMAX  equ 8 * 144           ; the largest BASE band: 64 x 144 on a
                                  ; fullscreen VGA, which is the tallest cell
                                  ; times three lanes
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
    mov ax, [ti_bw]
    mov [ti_spanw], ax              ; every span below is cut to the band
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

    call ti_dirty_build             ; ...and what each TRANSITION moves

    mov word [ti_pi], 0             ; ...and the mini unit that rides a card
.unit:
    mov ax, [ti_pi]
    cmp ax, TI_POSES
    jae .udone
    call ti_unit_build
    inc word [ti_pi]
    jmp short .unit
.udone:

    ; --- and the two players' bases, which are ONE band drawn twice ---------
    ; ONE CALL AND NOT A LOOP: the base builder does every pose itself, the
    ; mound once and a keep each, and it owns [ti_pi] while it does. Driving
    ; it from here the way the poses above are driven made it reset the
    ; caller's own counter, which is a hang with the gfx lock held.
    call ti_base_build
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; ti_row_dither - knock a composed ground row down to a 50% MID-TONE
; in:  DI = the row, AX = the CELL row it is, CX = bytes in it
; clobbers: nothing
;
; A 1bpp adapter has two colours, so a SOLID ground and a SOLID figure are the
; same colour and the figure disappears into the diamond it stands on - which
; is what a correct ground looked like the first time it was drawn. SPEC.md
; 39.4's dither is the mid-tone, and it is applied to the GROUND ONLY: the
; figure goes down solid afterwards and reads against it.
;
; THE PARITY IS THE CELL'S AND NOT THE BAND'S, so the cell's ground and the
; band's baked copy of it agree where they meet. Two facts from ti_layout make
; that free: [ti_insx] is rounded to a multiple of 8, so a band's byte columns
; line up with its cell's and one mask byte serves both, and every CH, RISE
; and HUD in the table is even, so no cell's origin flips the phase against
; another's.
; -----------------------------------------------------------------------------
ti_row_dither:
    push ax
    push bx
    push cx
    push di
    mov bl, 0AAh                    ; bit 7 is the LEFTMOST pixel (SPEC.md
    test al, 1                      ; 5.4.2), so an even row lights the even
    jz .have                        ; columns
    mov bl, 55h
.have:
    jcxz .out
.b:
    and [di], bl
    inc di
    loop .b
.out:
    pop di
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
    push ax
    mov ax, [ti_cw]                 ; the cell's own ground is cut to the CELL
    mov [ti_spanw], ax
    pop ax
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
    mov cx, [ti_cw]                 ; ...and the ground is a MID-TONE, so the
    shr cx, 1                       ; figure that stands on it has something
    shr cx, 1                       ; to read against
    shr cx, 1
    mov ax, [ti_ry]
    call ti_row_dither
    pop cx
    ret

; -----------------------------------------------------------------------------
; ti_dirty_build - the minimal covering band of every transition
; out: ti_dy[p], ti_dh[p] - the rows that differ between pose p-1 and pose p
; clobbers: AX, BX, CX, DX, SI, DI
;
; TITHE-PLAN 3.4.1, and it is the cheapest lever in the document: an idle pose
; differs from its neighbour in PART of the figure, not all of it, so the band
; that goes down is the box of WHAT CHANGED - one opaque self-erasing rectangle
; with its own ground baked in, exactly one rectangle shorter. 50% of the rows
; is -43% off every commit, measured.
;
; THE RECT IS THE TOOL'S AND NOT THE ARTIST'S, which is what makes it safe: it
; is diffed out of the two poses here, so a row outside it is byte-identical by
; construction rather than by somebody remembering. A row outside that was NOT
; identical would be a stale row on the glass - a figure with a torn edge that
; never repairs.
; -----------------------------------------------------------------------------
ti_dirty_build:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov word [ti_pi], 0
.pose:
    mov ax, [ti_pi]
    cmp ax, TI_POSES
    jae .done
    call ti_pose_addr               ; DI = the pose ARRIVED AT
    mov bx, di
    mov ax, [ti_pi]                 ; ...and the one before it
    dec ax
    and ax, TI_POSES - 1
    push word [ti_pi]
    mov [ti_pi], ax
    call ti_pose_addr
    pop word [ti_pi]
    mov si, di
    mov di, bx                      ; SI = from, DI = to

    xor cx, cx                      ; walk the rows, first differing to last
    mov word [ti_d0], 0FFFFh
    mov word [ti_d1], 0
.row:
    cmp cx, [ti_bh]
    jae .have
    push cx
    call ti_row_differs             ; CF=1 this row moved
    pop cx
    jnc .next
    cmp word [ti_d0], 0FFFFh
    jne .lo
    mov [ti_d0], cx
.lo:
    mov [ti_d1], cx
.next:
    inc cx
    jmp short .row
.have:
    mov di, [ti_pi]
    shl di, 1
    cmp word [ti_d0], 0FFFFh
    je .none
    mov ax, [ti_d0]
    mov [ti_dy + di], ax
    mov ax, [ti_d1]
    sub ax, [ti_d0]
    inc ax
    mov [ti_dh + di], ax
    jmp short .step
.none:
    mov word [ti_dy + di], 0        ; nothing moved: nothing to commit
    mov word [ti_dh + di], 0
.step:
    inc word [ti_pi]
    jmp .pose                       ; NEAR: the row walk sits between here and
                                    ; the top and a short jump will not reach
.done:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; ti_row_differs - CF=1 if row CX of the bands at SI and DI is not identical
; clobbers: AX, BX, DX, flags
ti_row_differs:
    push cx
    push si
    push di
    mov ax, cx
    mul word [ti_bs]
    add si, ax
    add di, ax
    mov cx, [ti_bs]
.b:
    or cx, cx
    jz .same
    mov al, [si]
    cmp al, [di]
    jne .diff
    inc si
    inc di
    dec cx
    jmp short .b
.diff:
    pop di
    pop si
    pop cx
    stc
    ret
.same:
    pop di
    pop si
    pop cx
    clc
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
    mov ax, [ti_bw]                 ; ti_cell_span left [ti_spanw] at the CELL
    mov [ti_spanw], ax              ; width; every span here is the BAND's
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

    ; --- THE CELL'S OWN GROUND, FIRST -----------------------------------
    ; SPEC.md 97.4: the band is ONE OPAQUE rectangle that INCLUDES ITS OWN
    ; GROUND, because drawing it back where it was is the erase. Without
    ; this the band is dark everywhere the figure is not, so every feature
    ; punches a BW x BH hole in the diamond it stands on - 64 of a
    ; Hercules cell's 120 columns, which reads as the diamond's top tip
    ; stopping dead three rows in and its two side tips floating either
    ; side of a black box.
    call ti_pose_ground

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
    ; AND ONLY THE TOP HALF OF IT MOVES. TITHE-PLAN 3.4.1 asks the art for
    ; transitions whose motion is LOCAL, and the first cut of this idle leaned
    ; every row - which is a dirty rect covering the whole band and a lever
    ; worth exactly nothing. A breathing figure moves its chest and head; its
    ; feet do not move at all.
    mov ax, [ti_bw]
    shr ax, 1                       ; AX = the band's centre
    push cx
    mov cx, [ti_bh]
    shr cx, 1
    cmp [ti_ry], cx
    pop cx                          ; `pop` writes no flags, so the compare
    jae .emit                       ; above still decides
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

; -----------------------------------------------------------------------------
; ti_pose_ground - the CELL's diamond, for band row [ti_ry], into the band
; in:  DI = the band row, [ti_ry] = the BAND row
; clobbers: nothing
;
; The band sits at ([ti_insx], [ti_insy]) inside its cell, so band row r is
; CELL row r + insy and the diamond's span has to shift LEFT by insx to land
; in band coordinates. Both of those are invisible in the middle of a figure
; and obvious at its edges, which is where this was read off the glass.
; -----------------------------------------------------------------------------
ti_pose_ground:
    push ax
    push bx
    push cx
    push dx
    mov ax, [ti_ry]
    add ax, [ti_insy]               ; the CELL row this band row covers
    cmp ax, [ti_ch]
    jae .out
    mov bx, [ti_ch]
    shr bx, 1                       ; BX = ch/2
    sub ax, bx
    jns .pos
    neg ax
.pos:                               ; AX = |row - ch/2|
    mov dx, [ti_cw]
    shr dx, 1
    mul dx                          ; DX:AX = |dy| * (cw/2)
    or bx, bx
    jnz .div
    inc bx
.div:
    div bx                          ; ...over ch/2
    mov cx, [ti_cw]
    shr cx, 1
    sub cx, ax                      ; CX = the half width, in CELL pixels
    jbe .out
    mov ax, [ti_cw]
    shr ax, 1
    sub ax, [ti_insx]               ; ...about the cell's centre expressed in
                                    ; BAND coordinates, which is the whole of
                                    ; what makes the two grounds line up
    call ti_pose_span
    mov cx, [ti_bs]                 ; the same mid-tone, at the same phase
    mov ax, [ti_ry]
    add ax, [ti_insy]
    call ti_row_dither
.out:
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; ti_pose_span - DI = the row, AX = centre, CX = half width
; Clips against [ti_spanw], which the CALLER sets once per composition: the
; figure and the cell ground are cut to [ti_bw] and a base to [ti_basew], and
; passing it in a register would need one this routine does not have spare.
ti_pose_span:
    push ax
    push bx
    push cx
    push dx
    mov dx, ax
    sub dx, cx                      ; DX = the first pixel, SIGNED
    add cx, cx                      ; CX = how many
    or dx, dx
    jns .ok
    add cx, dx                      ; A SPAN CLIPPED AT THE LEFT LOSES THOSE
    jle .out                        ; PIXELS: the count used to stay put while
    xor dx, dx                      ; the start was clamped to 0, so they were
                                    ; drawn back on at the right. The figure
                                    ; never clipped and the ground always does
.ok:
.px:
    or cx, cx
    jz .out
    cmp dx, [ti_spanw]
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
; ti_base_build - every pose of the CHOSEN base, out of tibases.inc
; in:  the layout is current; [ti_bart] = the candidate, [ti_gidx] = the surface
; clobbers: AX, BX, CX, DX, SI, DI
;
; THE ART IS DATA NOW (SPEC.md 97.2.1). It was drawn by arithmetic here - a
; dithered mound with a keep leaning on it - which was right while the only
; question was whether the LAYOUT worked. It is the wrong shape for choosing
; art: every candidate would be a procedural builder in 8086 that gets deleted
; the moment one is picked, and none of them could be looked at beside the
; others. tools/os88tithebase.py draws them on the host and emits this file,
; and it is the generator TITHE-PLAN 3's `art/base/... -> BASES.DAT` path
; starts from.
;
; A GROUND AND EIGHT MOVES, which is SPEC.md 97.5.1's own shape written down:
; one full band that every pose shares, and a small sub-band per pose carrying
; only what moves. Eight whole bands would be eight times the bytes for one
; picture plus a bell.
;
; THE MOVES ARE PURE OR, and the emitter ASSERTS it rather than this trusting
; it - a candidate whose motion cleared a ground pixel would lose it here in
; silence. Each sub-band's x is forced down to a byte and its width padded up,
; so this ORs whole bytes and needs no shifter.
; -----------------------------------------------------------------------------
ti_base_build:
    push es
    push ds
    pop es
    cld
    mov ax, [ti_bas]                ; the slot pitch, which is NOT TI_BASEMAX -
    mul word [ti_baseh]             ; that is the largest slot any geometry
    mov [ti_bslot], ax              ; asks for and this is the one in use

    mov ax, [ti_bart]               ; the record: candidate x surface
    mov bx, TI_BART_G
    mul bx
    add ax, [ti_gidx]
    shl ax, 1
    mov si, ti_bart_tab
    add si, ax
    mov si, [si]
    mov [ti_brec], si

    mov word [ti_pi], 0             ; --- THE GROUND, INTO SLOT 0 ------------
    call ti_base_addr
    push di
    mov si, [ti_brec]
    mov si, [si]
    mov cx, [ti_bslot]
    rep movsb
    pop di

    ; --- ...REPLICATED INTO THE REST ---------------------------------------
    ; SI trails DI by exactly one slot, so slot 1 is copied from 0, slot 2
    ; from the 1 just written, and so on: one `rep movsw` fills them all.
    mov si, di
    add di, [ti_bslot]
    mov cx, [ti_bslot]
    shr cx, 1
    mov ax, TI_BASEPOSES - 1
    mul cx
    mov cx, ax
    rep movsw
    test word [ti_bslot], 1         ; an odd slot leaves one byte a pose
    jz .moves
    mov cx, TI_BASEPOSES - 1
    rep movsb

.moves:                             ; --- ...AND EACH POSE'S MOVE ON TOP -----
    mov word [ti_pi], 0
.mp:
    mov ax, [ti_pi]
    cmp ax, TI_BASEPOSES
    jae .done
    call ti_base_move
    inc word [ti_pi]
    jmp short .mp
.done:
    mov word [ti_pi], 0
    pop es
    ret

; -----------------------------------------------------------------------------
; ti_base_move - OR pose [ti_pi]'s sub-band into its own slot
; clobbers: AX, BX, CX, DX, SI, DI
;
; The record is `db x, y, w, h` and then (w/8)*h packed bytes, with w = 0
; meaning this pose adds nothing at all - which is legal and is what a
; candidate whose motion is entirely inside its ground would emit.
; -----------------------------------------------------------------------------
ti_base_move:
    push es
    push ds
    pop es
    cld
    mov si, [ti_brec]               ; the pose's record
    mov ax, [ti_pi]
    inc ax                          ; +0 is the ground's pointer
    shl ax, 1
    add si, ax
    mov si, [si]
    mov al, [si + 2]                ; w
    xor ah, ah
    or ax, ax
    jz .out
    mov [ti_mw], ax
    shr ax, 1
    shr ax, 1
    shr ax, 1
    mov [ti_mb], ax                 ; ...in BYTES, w being a multiple of 8
    mov al, [si + 3]                ; h
    xor ah, ah
    mov [ti_mh], ax
    mov al, [si + 0]                ; x, likewise a multiple of 8
    xor ah, ah
    shr ax, 1
    shr ax, 1
    shr ax, 1
    mov [ti_mx], ax
    mov al, [si + 1]                ; y
    xor ah, ah
    mov [ti_my], ax
    add si, 4                       ; SI -> the bytes

    call ti_base_addr               ; DI = this pose's slot
    mov ax, [ti_my]
    mul word [ti_bas]
    add di, ax
    add di, [ti_mx]                 ; ...at the sub-band's own corner

    mov dx, [ti_mh]
.row:
    or dx, dx
    jz .out
    push di
    mov cx, [ti_mb]
.byte:
    lodsb
    or [di], al                     ; PURE OR - the ground stays where the
    inc di                          ; move does not reach
    loop .byte
    pop di
    add di, [ti_bas]
    dec dx
    jmp short .row
.out:
    pop es
    ret

; ti_base_addr - DI = the band of base frame [ti_pi]
ti_base_addr:
    push ax
    push dx
    mov ax, [ti_pi]
    and ax, TI_BASEPOSES - 1
    mul word [ti_bas]
    mul word [ti_baseh]             ; frame * stride * rows, and both halves
    mov di, ti_base                 ; of a base band fit 16 bits by TI_BASEMAX
    add di, ax
    pop dx
    pop ax
    ret

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

.left:
    mov ax, [ti_ox]                 ; 2. P1's base zone, left of the grid - a
    mov bx, [ti_by]                 ;    strip that did not exist while the
    mov cx, [ti_bx]                 ;    grid started at the content's edge
    dec cx
    mov dx, bx
    add dx, [ti_boardh]
    dec dx
    cmp cx, ax
    jb .right
    call OSAPI_GFX_FILL

.right:
    mov ax, [ti_bx]                 ; 3. P2's base zone and the card panel
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
    mov ax, [ti_ox]                 ; 4. what is left under the board
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

; -----------------------------------------------------------------------------
; ti_base_frame - THE BASE LANE: one base a frame, on a clock of its own
; Preserves every register.
;
; THREE BASES AND TWENTY CHARACTERS (SPEC.md 97.5.1). A frame of base art is
; drawn once for the whole game where a frame of character art is drawn twenty
; times, so frames for a base are the cheapest animation on this board - which
; is what pays for TI_BASEPOSES being four times TI_POSES and for this lane
; existing at all. The bases came OFF the idle wheel to get here: on it they
; were 2 of 23 features and moved at the same 3.5 fps as everything else, and
; giving them a better rate there would have been taken out of the figures'.
;
; ONE OF THE TWO A FRAME, ALTERNATING, so each plays at half the tick rate -
; 9.1 Hz - for one band's work a frame rather than two. The lane accrues
; TI_BASESHARE of a frame and spends it when a band fits, so a geometry whose
; base is tall enough not to fit drops to every other frame on its own
; arithmetic rather than stealing the idle's credit.
; -----------------------------------------------------------------------------
; -----------------------------------------------------------------------------
; ti_phase_seed - spread the features' clocks so NEIGHBOURS ARE NEVER IN STEP
; Preserves every register.
;
; Every clock started at zero and advanced when the wheel reached its feature,
; which sounds like it spreads them and does not: the wheel walks in INDEX
; order, so a pass gives a run of adjacent features one step each and the
; board breathes as a block. Twenty figures moving together read as one
; animation with twenty copies rather than as a crowd.
;
; THE SEED IS 2D AND NOT 1D, because adjacency on this board is not adjacency
; in the index: a cell's index is column x 5 + row (SPEC.md 97.3's shear), so
; the cells a player sees stacked are i and i+1 and the ones side by side are i
; and i+5. `(col + 2*row) mod TI_POSES` puts vertical neighbours HALF A CYCLE
; apart - the strongest separation there is - horizontal ones a quarter, and
; diagonals three quarters, so no pair of touching cells shares a phase at all.
;
; It is re-seeded at every layout, which is deliberate: the spread is a
; property of the design rather than of how long the program has been running,
; and a relayout that left the old phases would keep whatever drift the last
; arm produced.
; -----------------------------------------------------------------------------
ti_phase_seed:
    push ax
    push bx
    push cx
    push dx
    xor bx, bx
.cell:
    cmp bx, TI_CELLS
    jae .bases
    mov ax, bx
    xor dx, dx
    mov cx, TI_ROWS
    div cx                          ; AX = column, DX = row
    add ax, dx
    add ax, dx                      ; col + 2*row
    and al, TI_POSES - 1
    mov [bx + ti_clock], al
    inc bx
    jmp short .cell
.bases:
    cmp bx, TI_FEATURES             ; the card's own slot, and any feature a
    jae .done                       ; later wave adds: spread rather than left
    mov ax, bx                      ; at zero
    and al, TI_POSES - 1
    mov [bx + ti_clock], al
    inc bx
    jmp short .bases
.done:
    ; THE TWO BASES START HALF A CYCLE APART, which is the only phase
    ; separation available to a pair - and a phase alone would still have them
    ; moving in lockstep, which is what the cadence below is for.
    mov byte [ti_bclock], 0
    mov byte [ti_bclock + 1], TI_BASEPOSES / 2
    mov byte [ti_bturnacc], 0
    pop dx
    pop cx
    pop bx
    pop ax
    ret

ti_base_frame:
    push ax
    push bx
    push dx
    mov ax, [ti_baseh]              ; one band, at the model's own terms
    mul word [ti_rowus]
    add ax, [ti_arrus]
    mov bx, ti_bacc
    call ti_lane
    jc .out
    ; TWO CONSTANT RATES, AND NEITHER BASE EVER REPEATS A POSE. It was a
    ; per-base step accumulator - one advanced on every visit of the lane and
    ; the other on four visits in five - which is a different rate and is also
    ; a PAUSE: the fifth visit redrew the pose it had just drawn, so the
    ; picture held for four frames. That reads as a beat on a flag or a bell
    ; and reads as broken on a FLAME, which is the thing that should never
    ; stop.
    ;
    ; The split moved into the LANE instead. One base is committed a frame as
    ; before, but WHICH is a Bresenham of 7 in 15, so each base advances one
    ; pose on every visit it gets and only the spacing of those visits varies -
    ; base 0 every 1 to 2 frames, base 1 every 2 to 3. The longest hold falls
    ; from four frames to three, both rates are constant, and they differ by
    ; 1.14x: 0.80 s a cycle against 0.92.
    mov al, [ti_bturnacc]
    add al, TI_BTN
    xor bx, bx                      ; ...base 0 unless the accumulator fires
    cmp al, TI_BTD
    jb .turn
    sub al, TI_BTD
    inc bx
.turn:
    mov [ti_bturnacc], al
    push bx

    add bx, ti_bclock               ; its own phase counter, which nothing
    mov al, [bx]                    ; outside this lane advances
    inc al
    cmp al, TI_BASEPOSES
    jb .store
    xor al, al
.store:
    mov [bx], al
    inc word [ti_nbadv]             ; ...and it is UNCONDITIONAL, which is the
    sub bx, ti_bclock               ; property: every visit advances, so no
                                    ; commit ever redraws the pose it just
                                    ; drew. tests/titheframe.py asserts this
                                    ; against ti_nbase, because a cadence
                                    ; built out of SKIPPED steps is exactly
                                    ; what this replaced
.drawn:
    mov al, [bx + ti_bclock]
    xor ah, ah
    mov [ti_pi], ax
    pop bx
    mov ax, [ti_b1x]
    or bx, bx
    jz .draw
    mov ax, [ti_b2x]
.draw:
    call ti_base_draw
    inc word [ti_nbase]             ; the lane's own rate, counted rather than
.out:                               ; modelled - it is the one number that says
    pop dx                          ; the base runs on a clock the idle's
    pop bx                          ; share cannot move
    pop ax
    ret

; -----------------------------------------------------------------------------
; ti_base_all - both bases at their current poses, for a full repaint
; Preserves every register.
; -----------------------------------------------------------------------------
ti_base_all:
    push ax
    push bx
    xor bx, bx
.b:
    push bx
    mov al, [bx + ti_bclock]
    xor ah, ah
    mov [ti_pi], ax
    mov ax, [ti_b1x]
    or bx, bx
    jz .draw
    mov ax, [ti_b2x]
.draw:
    call ti_base_draw
    pop bx
    inc bx
    cmp bx, 2
    jb .b
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; ti_base_draw - one player's base, at AX = its x
; in:  AX = x (a multiple of 8), [ti_pi] = the frame
; clobbers: nothing
; -----------------------------------------------------------------------------
ti_base_draw:
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
    call ti_base_addr
    mov si, di
    mov bx, [ti_basey]
    cmp ax, [ti_b1x]                ; P2's base follows its own column's shear
    je .y
    mov bx, [ti_basey2]
.y:
    mov cx, [ti_basew]
    mov dx, [ti_baseh]
    mov bp, [ti_bas]
    call OSAPI_GFX_BLIT1
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
; ti_icon - one 8x8 stat icon, at AX = x (a multiple of 8), BX = y
; in:  SI -> the 8 rows, AL/AH already set as the pen by the caller
; Preserves every register.
;
; A NUMBER WITH NO ICON IS A NUMBER THE READER GUESSES THE MEANING OF, which is
; what the panel's bare cost digit was and what the cell's two stacked numbers
; were. Eight pixels square is what a glyph cell is, so an icon costs exactly
; one cell of the row it labels - and it is a BAND rather than a character
; because the system font has no coin, sword or shield in it.
;
; One blit each, and they are drawn only where the numbers are: with the board
; and with a card, never in a frame (SPEC.md 97.4.1).
; -----------------------------------------------------------------------------
ti_icon:
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
    mov cx, 8
    mov dx, 8
    mov bp, 1
    call OSAPI_GFX_BLIT1
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
; ti_u8 - AL as two decimal digits at ES:DI (DI advanced by 2)
; clobbers: AX, DI
; -----------------------------------------------------------------------------
ti_u8:
    push bx
    xor ah, ah
    mov bl, 10
    div bl                          ; AL = tens, AH = units
    add al, '0'
    stosb
    mov al, ah
    add al, '0'
    stosb
    pop bx
    ret

; -----------------------------------------------------------------------------
; ti_poke - copy the NUL string at SI into the HUD buffer at DI
; clobbers: AL, SI, DI
; -----------------------------------------------------------------------------
ti_poke:
    lodsb
    or al, al
    jz .out
    stosb
    jmp short ti_poke
.out:
    ret

; -----------------------------------------------------------------------------
; ti_hud_draw - the strip above the board: the round, the STATUS LINE and the
; FRONT/REAR toggle. Preserves every register.
;
; IT IS COMPOSED AND BLITTED ONCE, like a card (SPEC.md 97.4.1.1). It was one
; centred `OSAPI_FONT_RUN`, which is cheap and has one property that rules it
; out here: a run draws ONLY ITS OWN LENGTH, so a strip whose text changes
; length leaves the tail of the last one behind. That was survivable while the
; strip said `ROUND 03 PLAN` and is not now it carries an ABILITY LINE - one
; card's is forty characters and the next one's is fifty-three.
;
; THREE BLOCKS AND THE MIDDLE ONE IS THE VARIABLE: the round and phase hard
; left, the toggle hard right ABOVE THE PANEL IT BELONGS TO, and the status
; centred in what is left. The toggle is in the HUD and not in the panel
; because the panel has no row to give - Hercules' seven cards and the COMMIT
; row use its height to the pixel (97.4.2) - and because the HUD's own right
; hand end is directly over the hand it is about.
; -----------------------------------------------------------------------------
ti_hud_draw:
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

    ; THE BAND'S X IS ALIGNED AND THE CONTENT ORIGIN IS NOT NECESSARILY.
    ; `OSAPI_GFX_BLIT1` refuses an x that is not a multiple of 8 (SPEC.md
    ; 5.4.2) and WF_SNAP is best-effort, so a window the kernel could not snap
    ; leaves `ti_ox` odd - which is the trap ti_lay already carries its own
    ; note about, and which cost this strip its first two characters on a
    ; Hercules the first time it ran.
    mov ax, [ti_ox]
    add ax, 7
    and ax, 0FFF8h
    mov [ti_hx], ax
    sub ax, [ti_ox]
    mov cx, [ti_cw_box]
    sub cx, ax
    and cx, 0FFF8h
    mov [ti_hw], cx
    mov ax, cx                      ; the band is the whole strip
    mov cl, 3
    shr ax, cl
    inc ax                          ; ...plus ti_glyph's pad byte
    mov [ti_hbs], ax
    mul word [ti_hud]
    cmp ax, TI_HUDBANDMAX
    jbe .fit
    jmp .out                        ; a surface this wide cannot occur, but a
.fit:                               ; band that overran would be silent
    mov di, ti_hudband
    mov cx, ax
    push di
    xor al, al
    rep stosb
    pop di
    mov bp, [ti_hbs]

    mov ax, [ti_hud]                ; one line, centred in the strip
    sub ax, [ti_fh]
    shr ax, 1
    mov [ti_hty], ax

    ; --- hard left: the round and the phase --------------------------------
    mov di, ti_hudbuf
    mov si, ti_s_round
    call ti_poke
    mov al, [ti_round]
    call ti_u8
    mov si, ti_s_phase
    call ti_poke
    mov byte [di], 0
    mov di, ti_hudband
    mov bx, 4
    mov dx, [ti_hty]
    mov si, ti_hudbuf
    call ti_text
    mov [ti_hleft], bx

    ; --- hard right: the FRONT/REAR toggle, over the panel -----------------
    call ti_hud_toggle

    ; --- and the status, centred between them ------------------------------
    call ti_hb_status
    mov si, ti_hudband              ; ...then the WHOLE strip, this being the
    mov ax, [ti_hx]                 ; call that composed all three blocks
    mov bx, [ti_oy]
    mov cx, [ti_hw]
    mov dx, [ti_hud]
    mov bp, [ti_hbs]
    call OSAPI_GFX_BLIT1
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

; -----------------------------------------------------------------------------
; ti_hud_status - recompose and blit the MIDDLE BLOCK alone
; Preserves every register.
;
; A HOVER CHANGE MUST NOT COST THE WHOLE STRIP. It did, and the field reported
; it exactly: running the pointer down the card list took the idle animation
; to a crawl. Measured on a VGA at 4.9 frames a second against 18.7 parked,
; while sweeping the BOARD - the same twenty-cell walk, the same status
; change, no card redraw - stayed at 18.2. The strip is 640x36 = 23,040 pixels
; and a card is 128x32 = 4,096, so the strip was three quarters of the work of
; a hover and none of it had changed: the round, the phase and the toggle are
; the same bytes they were.
;
; So the band PERSISTS - it is bss, the other two blocks are still in it - and
; this recomposes the middle and blits that rectangle alone. Its x is snapped
; out to a byte each side, `gfx_blit1` refusing an unaligned one (SPEC.md
; 5.4.2), and the right edge gets one byte of slack because `ti_glyph` writes
; a pad byte past its last cell.
; -----------------------------------------------------------------------------
ti_hud_status:
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
    cmp word [ti_hbs], 0            ; nothing has composed the strip yet
    je .out
    mov bp, [ti_hbs]
    call ti_hb_status               ; ...which leaves the rectangle to put down
    cmp word [ti_hsw], 0
    je .out
    mov si, ti_hudband              ; ...and the band's own row and byte
    mov ax, [ti_hty]
    mul word [ti_hbs]
    add si, ax
    mov ax, [ti_hsx]
    mov cl, 3
    shr ax, cl
    add si, ax
    mov ax, [ti_hx]
    add ax, [ti_hsx]
    mov bx, [ti_oy]
    add bx, [ti_hty]
    mov cx, [ti_hsw]
    mov dx, [ti_fh]
    mov bp, [ti_hbs]
    call OSAPI_GFX_BLIT1
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

; --- ti_hb_status - the middle block INTO the band ---------------------------
; in:  BP = the band's stride
; out: [ti_hsx]/[ti_hsw] = the byte-snapped rectangle that needs putting down
;
; IT CLEARS THE BLOCK AND BLITS THE LINE. Those are two different rectangles
; on purpose: clearing is memory and blitting is a kernel arrival over a
; framebuffer, so the cheap one is done generously and the dear one is cut to
; what changed. The block is ~550 pixels of a VGA strip and an ability line is
; ~300 of them, and what has to be PUT DOWN is the union of the line that was
; there and the line replacing it - the old one being what would otherwise be
; left behind. Cutting the CLEAR to that union as well is where the first
; version went wrong, because the union's left edge is only meaningful once a
; line has been drawn at all.
ti_hb_status:
    push ax
    push bx
    push cx
    push dx
    push si
    push di

    ; --- where the line goes, and how wide it is ---------------------------
    call ti_status                  ; SI -> the line
    call ti_textw
    mov cx, [ti_hright]             ; the room the other two blocks left
    sub cx, [ti_hleft]
    jbe .none
    cmp cx, [ti_fw]                 ; ...less the cell ti_glyph pads with
    jbe .none
    sub cx, [ti_fw]
    cmp ax, cx
    jbe .mid
    mov bx, [ti_hleft]              ; ...and a line too long for it starts at
    add bx, [ti_fw]                 ; the left of that room rather than being
    mov ax, cx                      ; centred out of the window
    jmp short .have
.mid:
    sub cx, ax
    shr cx, 1
    mov bx, [ti_hleft]
    add bx, cx
.have:
    mov [ti_hnx], bx
    add ax, bx
    add ax, [ti_fw]                 ; ...plus ti_glyph's own pad cell
    mov [ti_hnr], ax

    ; --- CLEAR the whole block, which is memory and costs no arrival -------
    mov dx, [ti_hty]
.clr:
    mov ax, dx
    sub ax, [ti_hty]
    cmp ax, [ti_fh]
    jae .rect
    push dx                         ; ...DX, THE ROW, WHICH `mul` CLOBBERS.
    mov ax, dx                      ; It is the third time in this package: a
    mul bp                          ; multiply lands its high half there, so a
    pop dx                          ; loop that counts rows in DX and resolves
    mov di, ti_hudband              ; a row address inside itself clears
    add di, ax                      ; exactly ONE row and leaves the rest of
    mov ax, [ti_hleft]              ; the last line under the new one - which
    add ax, 7                       ; on the glass is a status strip with a
    mov cl, 3                       ; clean TOP pixel row and four garbled
    shr ax, cl                      ; ones under it. It clears from the first
    add di, ax                      ; WHOLE byte at or after the block's left
                                    ; edge and never the one that straddles it.
    mov ax, [ti_hright]
    sub ax, [ti_hleft]
    shr ax, cl                      ; ...and THE COUNT VIA AX, because
    mov cx, ax                      ; `mov cx, <count>` before `shr cx, cl`
    inc cx                          ; overwrites the 3 in CL that the shift
    xor al, al                      ; itself reads
    rep stosb
    inc dx
    jmp short .clr

    ; --- the rectangle to PUT DOWN: this line unioned with the last --------
.rect:
    mov bx, [ti_hnx]
    cmp bx, [ti_hpr]                ; ...and nothing to union with while the
    jb .l                           ; last box is empty
    cmp word [ti_hpr], 0
    je .l2
.l:
    cmp bx, [ti_hpx]
    jbe .l2
    mov bx, [ti_hpx]
.l2:
    mov ax, [ti_hnr]
    cmp ax, [ti_hpr]
    jae .r
    mov ax, [ti_hpr]
.r:
    cmp bx, [ti_hleft]              ; ...clamped to the block it belongs to
    jae .lc
    mov bx, [ti_hleft]
.lc:
    mov cx, [ti_hright]
    add cx, [ti_fw]
    cmp ax, cx
    jbe .rc
    mov ax, cx
.rc:
    and bx, 0FFF8h                  ; ...and snapped out to whole bytes, which
    add ax, 7                       ; gfx_blit1's one alignment rule wants
    and ax, 0FFF8h
    cmp ax, [ti_hw]
    jbe .clamp
    mov ax, [ti_hw]
.clamp:
    mov [ti_hsx], bx
    sub ax, bx
    jnc .keep
    xor ax, ax
.keep:
    mov [ti_hsw], ax

    mov ax, [ti_hnx]                ; this line's box becomes the last one's
    mov [ti_hpx], ax
    mov ax, [ti_hnr]
    mov [ti_hpr], ax

    mov di, ti_hudband              ; ...and then it is lettered
    mov bx, [ti_hnx]
    mov dx, [ti_hty]
    call ti_status
    call ti_text
    jmp short .out
.none:
    mov word [ti_hsw], 0
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; ti_hud_toggle - FRONT / REAR at the strip's right hand end
; in:  DI = the band, BP = its stride; out: [ti_hright] = where it starts
; Preserves every register.
;
; THE SELECTED ARM IS BOXED, not brightened: the strip is one bit deep on two
; adapters of three (SPEC.md 39.4), so a "highlight" there is either the same
; white or a dither nobody can read at six pixels. A box is legible on all
; three and is the same four lines on each.
;
; ITS HIT BOX IS BANKED IN SCREEN COORDINATES, because the click handler has
; no way to re-derive it: the arms are laid out from the RIGHT, so their x
; depends on the two words' own widths in whichever face is current.
; -----------------------------------------------------------------------------
ti_hud_toggle:
    push ax
    push bx
    push cx
    push dx
    push si
    mov si, ti_s_rear
    call ti_textw
    mov cx, [ti_hw]                 ; ...laid out from the right
    sub cx, 4
    sub cx, ax
    mov [ti_tg1x], cx
    mov si, ti_s_front
    call ti_textw
    sub cx, [ti_fw]
    sub cx, [ti_fw]
    sub cx, ax
    mov [ti_tg0x], cx
    sub cx, [ti_fw]                 ; ...TWO CELLS OF GAP, and like the left
    sub cx, [ti_fw]                 ; block's it is load-bearing: the status
    mov [ti_hright], cx             ; block clears a byte at a time and a
                                    ; glyph's pad cell past that, so a tighter
                                    ; gap takes the toggle's first letter and
                                    ; the left edge of its box with it

    mov bx, [ti_tg0x]
    mov dx, [ti_hty]
    mov si, ti_s_front
    call ti_text
    mov bx, [ti_tg1x]
    mov dx, [ti_hty]
    mov si, ti_s_rear
    call ti_text

    mov bx, [ti_tg0x]               ; the box, round whichever arm is selected
    mov si, ti_s_front
    cmp word [ti_row], TI_ROW_FRONT
    je .box
    mov bx, [ti_tg1x]
    mov si, ti_s_rear
.box:
    call ti_textw
    mov cx, bx
    add cx, ax
    call ti_hb_box
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; --- ti_hb_box - a frame round [BX, CX) of the HUD's own text line ----------
; It hangs one pixel outside the glyph cell on every side, which the strip has
; because ti_hty centres a single line in a HUD at least eight rows deeper.
ti_hb_box:
    push ax
    push bx
    push cx
    push dx
    dec bx
    inc cx
    mov dx, [ti_hty]
    dec dx
    call ti_hb_hline
    mov dx, [ti_hty]
    add dx, [ti_fh]
    call ti_hb_hline
    mov ax, bx
.side:
    mov bx, ax
    call ti_hb_set
    mov bx, cx
    call ti_hb_set
    dec dx
    cmp dx, [ti_hty]
    jae .side
    pop dx
    pop cx
    pop bx
    pop ax
    ret

ti_hb_hline:
    push bx
.x:
    cmp bx, cx
    ja .out
    call ti_hb_set
    inc bx
    jmp short .x
.out:
    pop bx
    ret

ti_hb_set:                          ; BX = x, DX = y, in the HUD band
    push ax
    push bx
    push cx
    push dx                         ; ...DX, WHICH `mul` CLOBBERS AND WHICH IS
                                    ; THE ROW (ti_cb_set's own note)
    push di
    cmp dx, [ti_hud]
    jae .out
    cmp bx, [ti_hw]
    jae .out
    mov ax, dx
    mul word [ti_hbs]
    mov di, ti_hudband
    add di, ax
    mov ax, bx
    mov cl, 3
    shr ax, cl
    add di, ax
    mov cx, bx
    and cx, 7
    mov al, 080h
    shr al, cl
    or [di], al
.out:
    pop di
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; ti_status - SI -> the line the HUD's middle block shows
; Preserves every register bar SI.
;
; THE POINTER PICKS IT (SPEC.md 97.4.8). A character has a special ability and
; a line of prose is the only way to say what it does, so the strip that says
; what ROUND it is becomes the strip that says what the thing under the pointer
; DOES - a card in the hand or a character on the board, the two being the same
; question asked in two places. With nothing hovered it says which base
; candidate is on screen, which is wave 1a's own business (97.2.1).
; -----------------------------------------------------------------------------
ti_status:
    push ax
    push bx
    push cx                         ; ...CX and DX, which the divide below uses
    push dx                         ; and which ti_hud_draw has already set up
    push di
    mov bx, [ti_hover]
    cmp bx, -1
    jne .card
    mov bx, [ti_hovc]
    cmp bx, -1
    je .base
    mov ax, bx                      ; a cell shows the card it would be, which
    xor dx, dx                      ; is wave 1a's fiction and is at least a
    mov bx, TI_HAND                 ; STABLE one - the same cell always names
    div bx                          ; the same character
    mov bx, dx
    jmp .cellline                   ; ...and the board's line NAMES it (97.4.8.1)
.card:
    mov ax, bx
    mov cl, TI_C_SIZE
    mul cl
    mov si, ti_cards
    add si, ax
    mov si, [si + TI_C_ABIL]
    jmp short .out
.cellline:
    ; A BOARD CHARACTER'S LINE IS `NAME  POWER  ABILITY` (SPEC.md 97.4.8.1).
    ;
    ; THE NAME IS WHY IT IS A LINE AND NOT A CAPTION. A card in the hand is
    ; lettered with its own name; a character on the BOARD is a 64-pixel
    ; figure and nothing else, so without this the player is reading the art
    ; to work out which character it is - which the art at this size cannot
    ; answer, and will not answer even when it is finished.
    ;
    ; AND THE POWER IS ALWAYS IN IT, not only where the cell's column has no
    ; row for one. Power is what a player wants while planning a KILL, and a
    ; kill is of something on the BOARD - so unlike a cost, which is only ever
    ; read with the card in hand, it has nowhere to fall back to. It was CGA's
    ; alone while the line was a bare ability; with a name in front the line is
    ; the character's identity rather than its footnote, and a character that
    ; has no special ability still has a line worth reading.
    push bx
    push word [ti_ci]
    mov ax, [ti_hovc]
    mov [ti_ci], ax
    call ti_cell_rec                ; SI -> the card behind that cell
    pop word [ti_ci]
    pop bx
    mov di, ti_hudbuf
    push si
    mov si, [si + TI_C_NAME]
    call ti_poke
    mov al, ' '
    stosb
    stosb
    pop si
    mov al, TI_IC_SOUL
    stosb
    mov al, [si + TI_C_PWR]
    call ti_u8
    mov al, ' '
    stosb
    stosb
    mov si, [si + TI_C_ABIL]
    call ti_poke
    mov byte [di], 0
    mov si, ti_hudbuf
    jmp short .out
.base:
    mov di, ti_hudbuf
    mov si, ti_s_bsep
    call ti_poke
    mov bx, [ti_bart]
    shl bx, 1
    mov si, [bx + ti_bart_name]
    call ti_poke
    mov byte [di], 0
    mov si, ti_hudbuf
.out:
    pop di
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; ti_res_draw - one player's resource block, in the shear's empty corner
; in:  AX = x, BX = y, CL = gold, CH = souls, SI = the side's label
; Preserves every register.
; -----------------------------------------------------------------------------
ti_res_draw:
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
    mov [ti_rx], ax
    mov [ti_ry2], bx
    mov [ti_rg], cl
    mov [ti_rs], ch
    mov [ti_rsw], dl

    ; A SHALLOW CORNER GOES SIDEWAYS. A CGA's lift is TWELVE pixels, which
    ; holds one glyph row - so stacking three fields there showed the first and
    ; refused the other two, and the board read as if a player had no souls and
    ; no swaps at all. Laid out across, that same row is 96 pixels wide (the
    ; strip above column 0, and the strip below column 3, are a cell wide where
    ; the shear leaves them), and the three fields need 80.
    ;
    ; THE LABEL IS WHAT PAYS FOR IT. "P1" and "P2" exist so two blocks on one
    ; board cannot be confused, and on a shallow corner they are three cells of
    ; the twelve there are - which is the difference between showing everything
    ; and showing a third of it. They are diagonally opposite and each sits
    ; beside its own base, so position says it.
    cmp word [ti_lift], 24
    jb .sideways

    mov di, ti_numbuf               ; the side's own label, so two blocks on
    call ti_poke                    ; one board cannot be confused
    mov byte [di], 0
    mov cx, [ti_rx]
    mov dx, [ti_ry2]
    mov si, ti_numbuf
    mov ax, (CBLACK << 8) | CWHITE
    call OSAPI_FONT_RUN

    mov ax, [ti_rx]                 ; GOLD, under the label
    mov bx, [ti_ry2]
    add bx, 8
    mov si, ti_ic_cost
    call ti_icon
    mov di, ti_numbuf
    mov al, [ti_rg]
    call ti_u8
    mov byte [di], 0
    mov cx, [ti_rx]
    add cx, 8
    mov dx, [ti_ry2]
    add dx, 8
    mov si, ti_numbuf
    mov ax, (CBLACK << 8) | CWHITE
    call OSAPI_FONT_RUN

    mov ax, [ti_rx]                 ; ...SOULS under that
    mov bx, [ti_ry2]
    add bx, 16
    mov si, ti_ic_soul
    call ti_icon
    mov di, ti_numbuf
    mov al, [ti_rs]
    call ti_u8
    mov byte [di], 0
    mov cx, [ti_rx]
    add cx, 8
    mov dx, [ti_ry2]
    add dx, 16
    mov si, ti_numbuf
    mov ax, (CBLACK << 8) | CWHITE
    call OSAPI_FONT_RUN
    jmp .swaps

.sideways:                          ; --- ONE ROW, THREE FIELDS, NO LABEL ----
    mov ax, [ti_rx]                 ; the coin at +0, its digits at +8
    mov bx, [ti_ry2]
    mov si, ti_ic_cost
    call ti_icon
    mov di, ti_numbuf
    mov al, [ti_rg]
    call ti_u8
    mov byte [di], 0
    mov cx, [ti_rx]
    add cx, 8
    mov dx, [ti_ry2]
    mov si, ti_numbuf
    mov ax, (CBLACK << 8) | CWHITE
    call OSAPI_FONT_RUN

    mov ax, [ti_rx]                 ; the skull at +32, its digits at +40
    add ax, 32
    mov bx, [ti_ry2]
    mov si, ti_ic_soul
    call ti_icon
    mov di, ti_numbuf
    mov al, [ti_rs]
    call ti_u8
    mov byte [di], 0
    mov cx, [ti_rx]
    add cx, 40
    mov dx, [ti_ry2]
    mov si, ti_numbuf
    mov ax, (CBLACK << 8) | CWHITE
    call OSAPI_FONT_RUN

    cmp byte [ti_rsw], 0FFh         ; ...and the swaps at +64, as "S n" - the
    je .out                         ; word does not fit and the number is what
    mov di, ti_numbuf               ; is read
    mov al, 'S'
    stosb
    mov al, [ti_rsw]
    add al, '0'
    stosb
    mov byte [di], 0
    mov cx, [ti_rx]
    add cx, 64
    mov dx, [ti_ry2]
    mov si, ti_numbuf
    mov ax, (CBLACK << 8) | CWHITE
    call OSAPI_FONT_RUN
    jmp .out

.swaps:
    cmp byte [ti_rsw], 0FFh         ; ...and the SWAPS, which is this player's
    je .out                         ; and not the panel's: it came off the
    cmp word [ti_lift], 32          ; COMMIT row when UNDO took the space
    jb .out
    mov di, ti_numbuf
    mov si, ti_s_swap
    call ti_poke
    mov al, [ti_rsw]
    add al, '0'
    stosb
    mov byte [di], 0
    mov cx, [ti_rx]
    mov dx, [ti_ry2]
    add dx, 24
    mov si, ti_numbuf
    mov ax, (CBLACK << 8) | CWHITE
    call OSAPI_FONT_RUN
.out:
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; ti_hp_draw - a player's HP, ABOVE their base
; in:  AX = the base's x, BX = the base's y, CL = hp
; Preserves every register.
; -----------------------------------------------------------------------------
ti_hp_draw:
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
    sub bx, 10                      ; clear of the base's own crest...
    push cx                         ; ...and CENTRED over it rather than hard
    mov cx, [ti_basew]              ; against its left edge: the block is an
    sub cx, 24                      ; icon and two digits, 24 pixels, and a
    shr cx, 1                       ; base is 48 to 72 wide
    and cx, 0FFF8h                  ; ...on the byte grid, so the run keeps
    add ax, cx                      ; SPEC.md 6.1's single-store path
    pop cx
    mov [ti_rx], ax
    mov [ti_ry2], bx
    mov [ti_rg], cl

    mov si, ti_ic_hp
    call ti_icon
    mov di, ti_numbuf
    mov al, [ti_rg]
    call ti_u8
    mov byte [di], 0
    mov cx, [ti_rx]
    add cx, 8
    mov dx, [ti_ry2]
    mov si, ti_numbuf
    mov ax, (CBLACK << 8) | CWHITE
    call OSAPI_FONT_RUN

    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; ti_cellnum - one cell's STAT COLUMN, composed in the package's own face
; in:  [ti_ci]; AX = the cell's x, BX = its y
; Preserves every register.
;
; TITHE-PLAN 3.8.1, and the whole reason the sprite band is the FIGURE's box:
; these change at most ONCE A ROUND while the sprite redraws every few frames,
; so carrying them inside the band would pay for them tens of times over. They
; sit in the cell's empty columns - [0, INSX) to the left of the band - which
; starts on a multiple of 8 because the cell's x and INSX both are.
;
; THE SMALL FACE IS WHAT PUTS FOUR STATS THERE (SPEC.md 97.4.1.1). The column
; is 24 pixels on every adapter, which is THREE cells of the system 8x8 -
; exactly one `icon + two digits` pair and nothing spare - against FOUR at 6x6,
; and the cell's height holds 6 rows where it held 4, or 3 where it held 2. So
; a character states its HP, both of its variable stats and its POWER, with the
; fourth cell of the first row left for the STANCE; and the question the owner
; put - another face, a mouse-over, or a whole-board toggle - is answered by
; the face on its own, with nothing to operate.
;
; WHICH PAIR OF VARIABLE STATS IS THE COLUMN'S OWN (TITHE-PLAN 5.2): front and
; rear are different roles, and a character on the board HAS a position, so the
; row is a fact here rather than the choice the hand's toggle makes.
;
; CGA IS ONE ROW SHORT AND POWER IS WHAT GOES (SPEC.md 97.4.8.1).
; -----------------------------------------------------------------------------
TI_CELLROWS equ 4                   ; HP, both variable stats, and POWER

ti_cellnum:
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
    mov [ti_nx], ax
    mov [ti_ny], bx

    mov ax, [ti_insx]               ; the band is the column, plus ti_glyph's
    mov cl, 3                       ; own pad byte
    shr ax, cl
    inc ax
    mov [ti_nbs], ax

    mov ax, [ti_ch]                 ; ...and as many rows as the cell holds
    sub ax, [ti_insy]
    jc .out
    xor dx, dx
    div word [ti_fh]
    cmp ax, TI_CELLROWS
    jbe .rok
    mov ax, TI_CELLROWS
.rok:
    or ax, ax
    jz .out
    mov [ti_nrows], ax
    mul word [ti_fh]
    mov [ti_nh], ax
    mul word [ti_nbs]
    cmp ax, TI_CELLBANDMAX
    ja .out
    mov cx, ax
    mov di, ti_cellband
    xor al, al
    rep stosb

    call ti_cell_rec                ; SI -> the card behind this cell, BX = the
    mov [ti_nrec], si               ; offset of its own row's stat pair
    mov [ti_nrow], bx
    mov di, ti_cellband
    mov bp, [ti_nbs]
    xor dx, dx

    mov si, [ti_nrec]               ; ROW 1 - the HP, and the STANCE beside it
    mov ah, [si + TI_C_HP]
    mov al, TI_IC_HP
    call ti_cn_pair
    call ti_cn_stance

    add dx, [ti_fh]                 ; ROW 2 and ROW 3 - the two that depend on
    mov si, [ti_nrec]               ; which row the character is standing in
    add si, [ti_nrow]
    mov ax, [si]
    call ti_cn_pair
    cmp word [ti_nrows], 3
    jb .put
    add dx, [ti_fh]
    mov si, [ti_nrec]
    add si, [ti_nrow]
    mov ax, [si + 2]
    call ti_cn_pair
    cmp word [ti_nrows], 4          ; ROW 4 - POWER, where there is a row for
    jb .put                         ; it; the pointer carries it where there
    add dx, [ti_fh]                 ; is not (SPEC.md 97.4.8.1)
    mov si, [ti_nrec]
    mov ah, [si + TI_C_PWR]
    mov al, TI_IC_SOUL
    call ti_cn_pair

.put:
    mov si, ti_cellband
    mov ax, [ti_nx]
    mov bx, [ti_ny]
    add bx, [ti_insy]
    mov cx, [ti_insx]
    mov dx, [ti_nh]
    mov bp, [ti_nbs]
    call OSAPI_GFX_BLIT1
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

; --- ti_cn_pair - one `icon value` pair at x=0 of band row DX ---------------
; in:  AL = the icon, AH = the value; DI = the band, BP = its stride
; Preserves every register.
ti_cn_pair:
    push ax
    push bx
    push cx
    push si
    push di
    push di
    mov di, ti_numbuf
    stosb                           ; the icon IS a glyph (tifaces.inc)
    mov al, ah
    call ti_u8
    mov byte [di], 0
    pop di
    xor bx, bx
    mov si, ti_numbuf
    call ti_text
    pop di
    pop si
    pop cx
    pop bx
    pop ax
    ret

; --- ti_cn_stance - the fourth cell of row 1, for a RANGED character --------
; A stance is FRONT or SNIPE (TITHE-PLAN 5.4) and only a shooter has one, so
; the cell is empty for everybody else - which is why there are TWO glyphs and
; not one: absent has to mean "not a shooter" and cannot also mean "FRONT".
ti_cn_stance:
    push ax
    push bx
    push cx
    push si
    push di
    mov si, [ti_nrec]
    add si, [ti_nrow]
    mov al, [si]                    ; ...ranged if either variable stat is
    cmp al, TI_IC_BOW               ; the bow
    je .yes
    mov al, [si + 2]
    cmp al, TI_IC_BOW
    jne .out
.yes:
    mov al, TI_IC_SFRONT            ; wave 1a has no orders behind it, so the
    mov bx, [ti_ci]                 ; stance is derived like every other number
    test bl, 4                      ; here - but it is STABLE, so the same cell
    jz .have                        ; always reads the same way
    mov al, TI_IC_SNIPE
.have:
    mov [ti_numbuf], al
    mov byte [ti_numbuf + 1], 0
    mov bx, [ti_fw]
    shl bx, 1
    add bx, [ti_fw]                 ; ...the fourth cell of the four
    mov si, ti_numbuf
    call ti_text
.out:
    pop di
    pop si
    pop cx
    pop bx
    pop ax
    ret

; --- ti_cell_rec - SI = the card behind cell [ti_ci], BX = its row's pair ----
; Wave 1a has no board state, so a cell names a card by its index and the
; COLUMN says which row it is standing in - columns 1 and 2 are the two front
; lines and 0 and 3 the two rears (SPEC.md 97.2.1). That is a fiction, but it
; is a stable one and it makes the front/rear split visible on the board, which
; is the thing the hand's toggle is about.
ti_cell_rec:
    push ax
    push cx
    push dx
    mov ax, [ti_ci]
    xor dx, dx
    mov cx, TI_ROWS
    div cx                          ; AL = the column, DL = the row in it
    push ax
    mov ax, [ti_ci]
    xor dx, dx
    mov cx, TI_HAND
    div cx
    mov ax, dx                      ; ...the card this cell shows
    mov cl, TI_C_SIZE
    mul cl
    mov si, ti_cards
    add si, ax
    pop ax
    mov bx, TI_C_RI1
    cmp al, 1
    je .front
    cmp al, 2
    jne .have
.front:
    mov bx, TI_C_FI1
.have:
    pop dx
    pop cx
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
    push ax
    push bx
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
    pop bx
    pop ax
    call ti_cellnum                 ; ...and its numbers AFTER the ground, which
                                    ; is the whole cell and would otherwise
                                    ; cover them
    inc word [ti_ci]
    jmp short .cell
.done:
    call ti_hud_draw
    mov ax, [ti_p1x]                ; each player's gold and souls, in the
    mov bx, [ti_p1y]                ; corner the shear left them
    mov cl, [ti_p1gold]
    mov ch, [ti_p1soul]
    mov dl, [ti_swaps]
    mov si, ti_s_p1
    call ti_res_draw
    mov ax, [ti_p2x]
    mov bx, [ti_p2y]
    mov cl, [ti_p2gold]
    mov ch, [ti_p2soul]
    mov dl, 0FFh                    ; the opponent's swaps are not ours to see
    mov si, ti_s_p2
    call ti_res_draw
    mov ax, [ti_b1x]                ; ...and their HP above their own base
    mov bx, [ti_basey]
    mov cl, [ti_p1hp]
    call ti_hp_draw
    mov ax, [ti_b2x]
    mov bx, [ti_basey2]
    mov cl, [ti_p2hp]
    call ti_hp_draw
    call ti_panel                   ; ...and the hand, which redraws with the
                                    ; board for the numbers' reason: nothing in
                                    ; it changes more than once a round bar the
                                    ; hovered row, and that one is a FEATURE
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
