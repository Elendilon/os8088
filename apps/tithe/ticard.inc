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

; a card record: cost, attack, defence, and a pointer to its name
TI_C_COST   equ 0
TI_C_ATK    equ 1
TI_C_DEF    equ 2
TI_C_NAME   equ 3
TI_C_SIZE   equ 5

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
    add ax, TI_CARDGAP              ; the COMMIT row included
    mov [ti_cardpitch], ax
    xor dx, dx
    mov ax, [ti_boardh]
    div word [ti_cardpitch]
    or ax, ax
    jz .none
    dec ax                          ; ...less the COMMIT row
    cmp ax, TI_HAND
    jbe .have
    mov ax, TI_HAND
.have:
    mov [ti_cardn], ax
    jmp short .out
.none:
    mov word [ti_cardn], 0
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

    ; --- line 1: a COIN, the cost, then the name ----------------------------
    ; The cost used to be a bare digit and TITHE-PLAN never said what it was a
    ; digit OF - gold, attack or anything else. Every number on a card and in a
    ; cell carries its icon now (SPEC.md 97.4.1).
    mov al, [ti_cink]
    mov ah, [ti_cpap]
    call OSAPI_GFX_BLIT1_PEN        ; the icons are INK on PAPER like the text,
                                    ; so a hovered card inverts whole
    mov ax, [ti_cbx]
    add ax, 8
    mov bx, [ti_cardy]
    add bx, 2
    mov si, ti_ic_cost
    call ti_icon

    mov di, ti_cardbuf
    mov si, [ti_cardp]
    mov al, [si + TI_C_COST]
    add al, '0'
    stosb
    mov al, ' '
    stosb
    mov si, [si + TI_C_NAME]
    call ti_poke
    mov byte [di], 0

    mov cx, [ti_cbx]
    add cx, 16                      ; inside the frame, past the icon, and
    mov dx, [ti_cardy]              ; still on the grid
    add dx, 2
    mov si, ti_cardbuf
    mov al, [ti_cink]
    mov ah, [ti_cpap]
    call OSAPI_FONT_RUN

    ; --- line 2: the stats, where the row is tall enough to carry one -------
    cmp word [ti_cardh], 20
    jb .pen0
    mov dx, [ti_cardy]
    add dx, [ti_cardh]
    sub dx, 10
    mov [ti_cardl2], dx

    mov ax, [ti_cbx]                ; a SWORD and the attack...
    add ax, 8
    mov bx, [ti_cardl2]
    mov si, ti_ic_atk
    call ti_icon
    mov di, ti_cardbuf
    mov si, [ti_cardp]
    mov al, [si + TI_C_ATK]
    call ti_u8
    mov byte [di], 0
    mov cx, [ti_cbx]
    add cx, 16
    mov dx, [ti_cardl2]
    mov si, ti_cardbuf
    mov al, [ti_cink]
    mov ah, [ti_cpap]
    call OSAPI_FONT_RUN

    mov ax, [ti_cbx]                ; ...then a SHIELD and the defence
    add ax, 40
    mov bx, [ti_cardl2]
    mov si, ti_ic_def
    call ti_icon
    mov di, ti_cardbuf
    mov si, [ti_cardp]
    mov al, [si + TI_C_DEF]
    call ti_u8
    mov byte [di], 0
    mov cx, [ti_cbx]
    add cx, 48
    mov dx, [ti_cardl2]
    mov si, ti_cardbuf
    mov al, [ti_cink]
    mov ah, [ti_cpap]
    call OSAPI_FONT_RUN
.pen0:
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

    mov di, ti_cardbuf              ; the swaps counter rides the COMMIT row
    mov si, ti_s_commit             ; rather than a strip of its own: it is one
    call ti_poke                    ; number and the row is already there
    mov al, [ti_swaps]
    add al, '0'
    stosb
    mov byte [di], 0

    mov cx, [ti_cardx]
    add cx, 8
    mov dx, [ti_cardy]
    add dx, 2
    mov si, ti_cardbuf
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
    call ti_panel_lay
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
