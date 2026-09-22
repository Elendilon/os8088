; =============================================================================
; os8088 - apps/tithe/ticard.inc
;
; THE CARD PANEL (SPEC.md 97.4.2, TITHE-PLAN 3.3). A vertical strip down the
; right-hand edge, not a row along the bottom: every row of board height the
; hand does not take is a row the five lanes get, and on a 640x200 CGA that is
; the difference between a board and a refusal.
;
; It holds the hand, the moused-over card expanded - which is the 23rd animated
; feature and the only one that is not a character - and the COMMIT row.
; =============================================================================

TI_HAND     equ 7                 ; cards in a hand (TITHE-PLAN 3.3)
TI_CARDGAP  equ 2
TI_NAMEMAX  equ 12
TI_UNITW    equ 24                ; the mini unit drawn ON a card - and the
TI_UNITHMAX equ 34                ; thing that animates when it is moused over
TI_UNITMAX  equ (TI_UNITW / 8) * TI_UNITHMAX

; a card record: cost, attack, defence, and a pointer to its name
TI_C_COST   equ 0
TI_C_ATK    equ 1
TI_C_DEF    equ 2
TI_C_NAME   equ 3
TI_C_SIZE   equ 5

; ti_stat - one icon-and-number pair on a card's second line
; in:  BX = the pair's x offset from [ti_cbx]+8, SI = the icon, AL = the
;      field's offset in the card record
; Preserves every register.
ti_stat:
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
    mov [ti_statx], bx
    mov bl, al
    xor bh, bh
    add bx, [ti_cardp]
    mov al, [bx]
    mov [ti_statv], al

    mov ax, [ti_cbx]
    add ax, 8
    add ax, [ti_statx]
    mov bx, [ti_cardl2]
    call ti_icon

    mov di, ti_numbuf
    mov al, [ti_statv]
    call ti_u8
    mov byte [di], 0
    mov cx, [ti_cbx]
    add cx, 16
    add cx, [ti_statx]
    mov dx, [ti_cardl2]
    mov si, ti_numbuf
    mov al, [ti_cink]
    mov ah, [ti_cpap]
    call OSAPI_FONT_RUN

    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; ti_clip - cut the NUL string at ti_cardbuf to BX characters
; clobbers: nothing
ti_clip:
    push bx
    push si
    mov si, ti_cardbuf
.n:
    or bx, bx
    jz .cut
    cmp byte [si], 0
    je .out
    inc si
    dec bx
    jmp short .n
.cut:
    mov byte [si], 0
.out:
    pop si
    pop bx
    ret

; -----------------------------------------------------------------------------
; ti_panel_lay - where the panel's rows are, from the layout
; out: [ti_cardx], [ti_cardw], [ti_cardn] set
; clobbers: nothing
;
; THE HAND IS ALWAYS SEVEN AND THE ROW HEIGHT IS WHAT MOVES. A panel that
; showed six cards on one adapter would be a different GAME there, not a
; smaller one, so CARDH is a layout-table field (SPEC.md 97.2) cut so that
; seven rows and the COMMIT row fit the board's own height.
; -----------------------------------------------------------------------------
ti_panel_lay:
    push ax
    push dx
    mov ax, [ti_panx]
    add ax, 8                       ; a margin each side, and the panel's x is
    mov [ti_cardx], ax              ; already a multiple of 8, so a card's is
    mov ax, [ti_pan]
    sub ax, 16
    mov [ti_cardw], ax
    mov ax, [ti_cardh]              ; how many rows the board's height holds,
    add ax, TI_CARDGAP              ; the button row included
    mov [ti_cardpitch], ax
    mov ax, [ti_cardh]              ; THE BUTTON ROW SITS LOWER, off the hand
    shr ax, 1                       ; by half a card: a COMMIT flush against
    mov [ti_cgap], ax               ; the last card reads as an eighth card
    xor dx, dx
    mov ax, [ti_boardh]
    sub ax, [ti_cgap]
    jnc .div
    xor ax, ax
.div:
    div word [ti_cardpitch]
    or ax, ax
    jz .none
    dec ax                          ; ...less the button row
    cmp ax, TI_HAND
    jbe .have
    mov ax, TI_HAND
.have:
    mov [ti_cardn], ax
    mov ax, [ti_cardh]              ; the unit that rides each card
    sub ax, 4
    cmp ax, TI_UNITHMAX
    jbe .uok
    mov ax, TI_UNITHMAX
.uok:
    or ax, ax
    jnz .uh
    inc ax
.uh:
    mov [ti_unith], ax
    jmp short .out
.none:
    mov word [ti_cardn], 0
    mov word [ti_unith], 1
.out:
    pop dx
    pop ax
    ret

; -----------------------------------------------------------------------------
; ti_card_y - BX = the top of hand row AX
; clobbers: AX, BX, flags
; -----------------------------------------------------------------------------
ti_card_y:
    push dx
    mul word [ti_cardpitch]
    add ax, [ti_by]
    mov bx, ax
    pop dx
    ret

; -----------------------------------------------------------------------------
; ti_card_draw - one hand row, at AX = its index
; Preserves every register.
;
; A CARD IS WHITE AND THE BOARD IS BLACK, which is the whole of how it reads at
; 1bpp: paper and ink swap for the hovered one, so the expansion needs no
; second colour and no dither. Every run is font_run - the frame, the ground
; and the glyphs are never drawn twice over each other (PERFORMANCE.md rule 2).
; -----------------------------------------------------------------------------
ti_card_draw:
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

    mov [ti_cardi], ax
    call ti_card_y                  ; BX = the row's top
    mov [ti_cardy], bx

    mov si, ti_cards                ; SI -> this card's record
    mov ax, [ti_cardi]
    mov cl, TI_C_SIZE
    mul cl
    add si, ax
    mov [ti_cardp], si

    ; --- HOVERED: inverted, WIDER, and pulsing ------------------------------
    ; TITHE-PLAN 3.3's "the moused-over one expanded and animated - the 23rd
    ; feature". It grows sideways into the panel's own 8-pixel margins and not
    ; downward, which is what keeps it off its neighbours: an expansion that
    ; overlapped them would need two cards repainted on every un-hover, where
    ; this needs the margin blacked and nothing else. Both edges stay on the
    ; byte grid, the panel's x being a multiple of 8.
    mov al, CWHITE
    mov ah, CBLACK
    mov word [ti_cx], 0             ; 0 = the inset card, 1 = the expanded one
    mov word [ti_c1off], 0          ; ...and whether line 1 carries a coin
    cmp word [ti_cardh], 20
    jae .h0
    mov word [ti_c1off], 8
.h0:
    cmp word [ti_hover], -1
    je .pen
    mov cx, [ti_hover]
    cmp cx, [ti_cardi]
    jne .pen
    mov al, CBLACK
    mov ah, CWHITE
    mov word [ti_cx], 1
.pen:
    mov [ti_cink], al
    mov [ti_cpap], ah

    mov al, CBLACK                  ; the panel's own row, so the margins an
    call OSAPI_SET_COLOR            ; expansion may have covered come back
    mov ax, [ti_panx]
    mov bx, [ti_cardy]
    mov cx, ax
    add cx, [ti_pan]
    dec cx
    mov dx, bx
    add dx, [ti_cardh]
    dec dx
    call OSAPI_GFX_FILL

    mov ax, [ti_cardx]              ; ...then the card, inset or full-width
    mov cx, [ti_cardw]
    cmp word [ti_cx], 0
    je .box
    mov ax, [ti_panx]
    mov cx, [ti_pan]
.box:
    mov [ti_cbx], ax
    mov [ti_cbw], cx

    mov al, [ti_cpap]
    call OSAPI_SET_COLOR
    mov ax, [ti_cbx]
    mov bx, [ti_cardy]
    mov cx, ax
    add cx, [ti_cbw]
    dec cx
    mov dx, bx
    add dx, [ti_cardh]
    dec dx
    call OSAPI_GFX_FILL
    mov al, [ti_cink]
    call OSAPI_SET_COLOR
    mov ax, [ti_cbx]
    mov bx, [ti_cardy]
    mov cx, ax
    add cx, [ti_cbw]
    dec cx
    mov dx, bx
    add dx, [ti_cardh]
    dec dx
    call OSAPI_GFX_FRAME

    cmp word [ti_cx], 0             ; the PULSE: a second frame that comes and
    je .body                        ; goes on the same clock the figures idle
    mov bx, [ti_cardi]              ; on, so the hovered card is animated and
    add bx, ti_clock                ; not merely different
    test byte [bx], 1
    jz .body
    mov ax, [ti_cbx]
    add ax, 2
    mov bx, [ti_cardy]
    add bx, 2
    mov cx, [ti_cbx]
    add cx, [ti_cbw]
    sub cx, 3
    mov dx, [ti_cardy]
    add dx, [ti_cardh]
    sub dx, 3
    call OSAPI_GFX_FRAME
.body:

    ; --- LINE 1 IS THE NAME, AND NOTHING ELSE -------------------------------
    ; A card is fourteen glyph cells wide on a VGA and the unit takes three of
    ; them, so a line carrying an icon, a cost, a space and a name lost the
    ; name's last letters - PIKEMA, ACOLYT, BULWAR. The cost went down to the
    ; stat line, where it belongs anyway: cost, attack and defence are the
    ; three numbers a player compares between cards.
    mov al, [ti_cink]
    mov ah, [ti_cpap]
    call OSAPI_GFX_BLIT1_PEN        ; the icons are INK on PAPER like the text,
                                    ; so a hovered card inverts whole
    mov di, ti_cardbuf
    mov si, [ti_cardp]
    cmp word [ti_cardh], 20         ; a card too short for a second line puts
    jae .name                       ; its COST in front of the name, that being
    mov al, [si + TI_C_COST]        ; the number that decides whether a card is
    call ti_u8                      ; playable at all
    mov al, ' '
    stosb
    mov si, [ti_cardp]
.name:
    mov si, [si + TI_C_NAME]
    call ti_poke
    mov byte [di], 0
    push bx
    mov bx, [ti_cbw]                ; ...cut to what is left once the unit has
    sub bx, 8 + TI_UNITW + 8        ; its corner and the icon its cell
    sub bx, [ti_c1off]
    shr bx, 1
    shr bx, 1
    shr bx, 1
    call ti_clip
    pop bx

    cmp word [ti_c1off], 0          ; the coin FIRST, so the name's run does
    je .run1                        ; not have to land on top of it - drawn
    mov ax, [ti_cbx]                ; after, it ate the name's first letter
    add ax, 8
    mov bx, [ti_cardy]
    add bx, 1
    mov si, ti_ic_cost
    call ti_icon
.run1:
    mov cx, [ti_cbx]
    add cx, 8
    add cx, [ti_c1off]              ; past the coin, where there is one
    mov dx, [ti_cardy]
    add dx, 2
    mov si, ti_cardbuf
    mov al, [ti_cink]
    mov ah, [ti_cpap]
    call OSAPI_FONT_RUN

    ; --- LINE 2: cost, attack, defence, each with its icon ------------------
    cmp word [ti_cardh], 20
    jb .short
    mov dx, [ti_cardy]
    add dx, [ti_cardh]
    sub dx, 10
    mov [ti_cardl2], dx
    mov bx, 0                       ; the three pairs, at 24 pixels each
    mov si, ti_ic_cost
    mov al, TI_C_COST
    call ti_stat
    mov bx, 24
    mov si, ti_ic_atk
    mov al, TI_C_ATK
    call ti_stat
    mov bx, 48
    mov si, ti_ic_def
    mov al, TI_C_DEF
    call ti_stat
    jmp short .pen0
.short:
.pen0:
    push word [ti_pi]               ; the unit itself, at this card's own pose
    mov bx, [ti_cardi]
    add bx, ti_clock
    mov bl, [bx]
    xor bh, bh
    mov [ti_pi], bx
    call ti_unit_draw
    pop word [ti_pi]

    cmp word [ti_cx], 0             ; ...and the hovered card's box is banked,
    je .pen1                        ; so the wheel can redraw the UNIT alone
    mov ax, [ti_cbx]                ; rather than the whole card
    mov [ti_hovbx], ax
    mov ax, [ti_cbw]
    mov [ti_hovbw], ax
    mov ax, [ti_cardy]
    mov [ti_hovy], ax
.pen1:
    mov ax, (CBLACK << 8) | CWHITE  ; the pen is valid for this lock hold
    call OSAPI_GFX_BLIT1_PEN        ; (SPEC.md 5.4.2.2), so it is put back
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
; ti_unit_build - the mini unit that rides a card, one frame per pose
; in:  [ti_pi]; the layout is current
; clobbers: AX, BX, CX, DX, SI, DI
;
; THE CARD'S OWN ANIMATION (TITHE-PLAN 3.3). A hovered card was a pulsing
; frame, which is a state change dressed as movement; what the panel wants is
; the unit ON the card moving, which is also what says which unit the card
; plays. One 16-pixel band a pose, drawn with the card's pen so it inverts
; with everything else.
; -----------------------------------------------------------------------------
ti_unit_build:
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
    mov word [ti_spanw], TI_UNITW
    call ti_unit_addr
    push di
    mov cx, TI_UNITMAX
    xor ax, ax
    rep stosb
    pop di

    mov word [ti_ury], 0
.row:
    mov ax, [ti_ury]
    cmp ax, [ti_unith]
    jae .done
    push di
    mul word [ti_unitb]
    add di, ax

    ; THE SAME SHAPE AS THE BOARD'S FIGURE, at a quarter of the size - head
    ; for the top eighth, then a body widest at the shoulders and tapering to
    ; the feet. It has to read as the unit the card PLAYS, so a shape of its
    ; own would be a second character; the first cut widened downward and read
    ; as a wedge.
    mov ax, [ti_unith]
    shr ax, 1
    shr ax, 1
    shr ax, 1                       ; AX = h/8, the head's depth
    mov bx, ax
    or bx, bx
    jnz .hd
    inc bx
.hd:
    mov ax, [ti_ury]
    cmp ax, bx
    jae .body
    mov cx, bx                      ; the head: a small constant width
    shr cx, 1
    inc cx
    inc cx
    jmp short .emit
.body:
    mov dx, TI_UNITW
    shr dx, 1
    shr dx, 1                       ; DX = w/4
    push dx
    mov ax, [ti_ury]
    mul dx
    mov cx, [ti_unith]
    or cx, cx
    jnz .bdiv
    inc cx
.bdiv:
    xor dx, dx
    div cx
    shr ax, 1
    pop dx
    sub dx, ax
    inc dx
    mov cx, dx                      ; CX = the half width
.emit:
    mov ax, TI_UNITW / 2
    cmp word [ti_ury], bx           ; the LEAN is the pose, and only the top
    jae .put                        ; moves - the dirty rect's rule applies to
    add ax, [ti_pi]                 ; a card's unit exactly as it does to a
    dec ax                          ; figure on the board
.put:
    call ti_pose_span
    pop di
    inc word [ti_ury]
    jmp short .row
.done:
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; ti_unit_addr - DI = the band of unit frame [ti_pi]
ti_unit_addr:
    push ax
    push dx
    mov ax, [ti_pi]
    and ax, TI_POSES - 1
    mul word [ti_unitb]
    mul word [ti_unith]
    mov di, ti_unit
    add di, ax
    pop dx
    pop ax
    ret

; -----------------------------------------------------------------------------
; ti_unit_draw - the unit on the card whose box is [ti_cbx]/[ti_cardy]
; in:  [ti_pi] = the frame; the pen already set by the caller
; Preserves every register.
; -----------------------------------------------------------------------------
ti_unit_draw:
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
    call ti_unit_addr
    mov si, di
    mov ax, [ti_cbx]
    add ax, [ti_cbw]
    sub ax, TI_UNITW
    sub ax, 8                       ; a margin inside the frame; every term is
    mov bx, [ti_cardy]              ; a multiple of 8, so the band's x is
    add bx, 2
    mov cx, TI_UNITW
    mov dx, [ti_unith]
    mov bp, [ti_unitb]
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
; ti_commit_draw - the COMMIT row, under the hand
; Preserves every register.
; -----------------------------------------------------------------------------
ti_commit_draw:
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

    mov ax, [ti_cardn]
    call ti_card_y
    add bx, [ti_cgap]
    mov [ti_cardy], bx

    mov al, CBLACK
    call OSAPI_SET_COLOR
    mov ax, [ti_cardx]
    mov bx, [ti_cardy]
    mov cx, ax
    add cx, [ti_cardw]
    dec cx
    mov dx, bx
    add dx, [ti_cardh]
    dec dx
    call OSAPI_GFX_FILL
    mov al, CWHITE
    call OSAPI_SET_COLOR
    mov ax, [ti_cardx]
    mov bx, [ti_cardy]
    mov cx, ax
    add cx, [ti_cardw]
    dec cx
    mov dx, bx
    add dx, [ti_cardh]
    dec dx
    call OSAPI_GFX_FRAME

    mov di, ti_cardbuf              ; COMMIT alone: the swaps counter used to
    mov si, ti_s_commit             ; ride this row and there is no longer room
    call ti_poke                    ; for it beside UNDO, so it has gone where
    mov byte [di], 0                ; it belongs - into the player's own
                                    ; resource block, beside their gold
    mov cx, [ti_cardx]
    add cx, [ti_undow]              ; ...past UNDO, which shares the row
    add cx, 12
    mov dx, [ti_cardy]
    add dx, 2
    mov si, ti_cardbuf
    mov ax, (CBLACK << 8) | CWHITE
    call OSAPI_FONT_RUN

    ; --- UNDO: A BUTTON AND NOT A CARD, so it is cut to its own label -------
    ; A plan is editable (TITHE-PLAN 5.0.2), so there has to be a way to take
    ; an entry back - and making it card-sized would say it was one of the
    ; seven. It rides the COMMIT row at the width of the word.
    mov al, CWHITE
    call OSAPI_SET_COLOR
    mov ax, [ti_cardx]
    mov bx, [ti_cardy]
    mov cx, ax
    add cx, [ti_undow]
    dec cx
    mov dx, bx
    add dx, [ti_cardh]
    dec dx
    call OSAPI_GFX_FRAME
    mov cx, [ti_cardx]
    add cx, 8
    mov dx, [ti_cardy]
    add dx, 2
    mov si, ti_s_undo
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
; ti_panel - the whole panel, with the board
; Preserves every register.
; -----------------------------------------------------------------------------
ti_panel:
    push ax
    push cx
    xor ax, ax
.row:
    cmp ax, [ti_cardn]
    jae .done
    push ax
    call ti_card_draw
    pop ax
    inc ax
    jmp short .row
.done:
    call ti_commit_draw
    pop cx
    pop ax
    ret

; -----------------------------------------------------------------------------
; ti_hover_ck - which card is the pointer over? (the 23rd feature's input)
; out: [ti_hover] updated; CF=1 it CHANGED
; Preserves every register bar the flags.
;
; OSAPI_MOUSE IS POLLED FROM THE WORKER and there is no hover callback to
; install - SPEC.md 12.8's event set has none, so a package that wants a hover
; asks. It costs one far call a frame, against the 23 the frame already makes.
; -----------------------------------------------------------------------------
ti_hover_ck:
    push ax
    push bx
    push cx
    push dx
    call OSAPI_MOUSE                ; CX = x, DX = y
    mov ax, -1
    cmp cx, [ti_cardx]
    jb .have
    mov bx, [ti_cardx]
    add bx, [ti_cardw]
    cmp cx, bx
    jae .have
    mov bx, [ti_by]
    cmp dx, bx
    jb .have
    sub dx, bx
    mov ax, dx
    xor dx, dx
    div word [ti_cardpitch]
    cmp ax, [ti_cardn]
    jb .have
    mov ax, -1
.have:
    cmp ax, [ti_hover]
    je .same
    mov bx, [ti_hover]              ; the row that LOST the hover has to be put
    mov [ti_hovold], bx             ; back too, and only the caller knows it is
    mov [ti_hover], ax              ; safe to draw
    pop dx
    pop cx
    pop bx
    pop ax
    stc
    ret
.same:
    pop dx
    pop cx
    pop bx
    pop ax
    clc
    ret
