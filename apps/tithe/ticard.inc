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

; the seven icons, which are glyphs 1..7 of every face (tools/os88titheface.py)
TI_IC_HP    equ 1
TI_IC_GOLD  equ 2
TI_IC_SOUL  equ 3
TI_IC_MELEE equ 4
TI_IC_SHIELD equ 5
TI_IC_BOW   equ 6
TI_IC_STAR  equ 7

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
    xor dx, dx                      ; by a THIRD of a card: a COMMIT flush
    mov cx, 3                       ; against the last card reads as an eighth
    div cx                          ; card, and half of one cost Hercules the
    mov [ti_cgap], ax               ; row that holds its stats
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
    mov word [ti_cpad], 1           ; THE HOVERED CARD'S SECOND FRAME NEEDS A
    cmp word [ti_cardh], 20         ; ROW AT EACH END and a card too short for
    jae .pad                        ; a stat line has not got one to give, so
    mov word [ti_cpad], 0           ; that geometry keeps the single frame
.pad:
    mov ax, [ti_cardh]              ; the unit that rides each card
    sub ax, 4
    sub ax, [ti_cpad]               ; ...INSIDE the inner frame rather than ON
    sub ax, [ti_cpad]               ; it: the band is OPAQUE, so a unit that
                                    ; reached the frame's own rows erased them
                                    ; across its width and the outline came
                                    ; back BROKEN
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
; ti_card_draw - one hand row, at AX = its index: COMPOSED, then ONE blit
; Preserves every register.
;
; IT WAS A DOZEN ARRIVALS. Two fills, a frame, a second frame, two font runs,
; three icon blits and the unit band - and at SPEC.md 97.5's measured ~800 us a
; call that is most of a frame for one card, seven of them for a repaint. The
; card is built in a band here and put down with ONE `OSAPI_GFX_BLIT1`.
;
; THE REASON IS THE FACE AND NOT THE SPEED (SPEC.md 97.4.1). `OSAPI_FONT_RUN`
; draws the system 8x8 and no other, so a smaller face means drawing the text
; ourselves - and once the text is being composed, composing the frame and the
; icons with it is less code than not.
;
; THE BAND IS ONE BYTE WIDER THAN THE CARD. `ti_glyph` places a glyph at any x
; by shifting it across a byte PAIR, so the last glyph on a row writes one byte
; past the card's own width; the pad is where that byte goes, and the blit is
; told the real width.
; -----------------------------------------------------------------------------
ti_card_draw:
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

    mov [ti_cardi], ax
    call ti_card_y                  ; BX = the row's top
    mov [ti_cardy], bx

    mov si, ti_cards                ; SI -> this card's record
    mov ax, [ti_cardi]
    mov cl, TI_C_SIZE
    mul cl
    add si, ax
    mov [ti_cardp], si

    ; --- hovered? then it is WIDER, and inverted at the blit ---------------
    mov word [ti_cx], 0
    cmp word [ti_hover], -1
    je .box
    mov cx, [ti_hover]
    cmp cx, [ti_cardi]
    jne .box
    mov word [ti_cx], 1
.box:
    mov ax, [ti_cardx]
    mov cx, [ti_cardw]
    cmp word [ti_cx], 0
    je .have
    mov ax, [ti_panx]
    mov cx, [ti_pan]
.have:
    mov [ti_cbx], ax
    mov [ti_cbw], cx
    shr cx, 1
    shr cx, 1
    shr cx, 1
    inc cx                          ; ...the pad byte ti_glyph writes into
    mov [ti_cbs], cx

    mov di, ti_cardband             ; a clean band
    mov ax, [ti_cbs]
    mul word [ti_cardh]
    mov cx, ax
    push di
    xor al, al
    rep stosb
    pop di

    ; --- the frame, and the pulse-free second one --------------------------
    call ti_cb_frame
    cmp word [ti_cx], 0
    je .text
    cmp word [ti_cpad], 0
    je .text
    call ti_cb_frame2
.text:
    call ti_cb_text
    call ti_cb_unit

    ; --- ONE ARRIVAL ------------------------------------------------------
    ; A hovered card is INK ON PAPER the other way round, which the PEN does
    ; rather than a second composition: the band is the same bits either way.
    mov ax, (CWHITE << 8) | CBLACK
    cmp word [ti_cx], 0
    je .pen
    mov ax, (CBLACK << 8) | CWHITE
.pen:
    call OSAPI_GFX_BLIT1_PEN
    mov si, ti_cardband
    mov ax, [ti_cbx]
    mov bx, [ti_cardy]
    mov cx, [ti_cbw]
    mov dx, [ti_cardh]
    mov bp, [ti_cbs]
    call OSAPI_GFX_BLIT1
    mov ax, (CBLACK << 8) | CWHITE  ; the pen is valid for this lock hold
    call OSAPI_GFX_BLIT1_PEN        ; (SPEC.md 5.4.2.2), so it is put back

    cmp word [ti_cx], 0             ; the hovered card's box is banked, so the
    je .out                         ; wheel can redraw the UNIT alone
    mov ax, [ti_cbx]
    mov [ti_hovbx], ax
    mov ax, [ti_cbw]
    mov [ti_hovbw], ax
    mov ax, [ti_cardy]
    mov [ti_hovy], ax
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

; --- ti_cb_set / ti_cb_frame - the band's own primitives ---------------------
; A pixel and a frame, in the band rather than on the screen. They are here and
; not in os88gfx.inc because a band this small wants no clipping and no stride
; arithmetic beyond one multiply (SPEC.md 5.12's own test: a shim would be
; longer than the body).
ti_cb_set:                          ; BX = x, DX = y
    push ax
    push bx
    push cx
    push dx                         ; ...DX, WHICH IS THE ROW. `mul` lands its
                                    ; high half there, so a body that resolves
                                    ; the row and then forgets it hands its
                                    ; CALLER a destroyed y - and every caller
                                    ; here loops on one. ti_cb_hline still
                                    ; terminates (it counts BX) and writes the
                                    ; rest of its run at an offset of tens of
                                    ; thousands, which is not a wrong line, it
                                    ; is the package's own memory. ti_glyph
                                    ; carries the same warning for the same
                                    ; reason; this is the site it was not
                                    ; applied to.
    push di
    cmp dx, [ti_cardh]              ; a band write is unclipped, so the band's
    jae .out                        ; own height is the fence
    cmp bx, [ti_cbw]
    jae .out
    mov ax, dx
    mul word [ti_cbs]
    mov di, ti_cardband
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

ti_cb_hline:                        ; BX = x0, CX = x1, DX = y
    push bx
.x:
    cmp bx, cx
    ja .out
    call ti_cb_set
    inc bx
    jmp short .x
.out:
    pop bx
    ret

ti_cb_frame:
    push bx
    push cx
    push dx
    push si
    xor bx, bx
    mov cx, [ti_cbw]
    dec cx
    xor dx, dx
    call ti_cb_hline                ; the top...
    mov dx, [ti_cardh]
    dec dx
    call ti_cb_hline                ; ...the foot...
    xor dx, dx
.side:                              ; ...and the two uprights
    cmp dx, [ti_cardh]
    jae .out
    xor bx, bx
    call ti_cb_set
    mov bx, [ti_cbw]
    dec bx
    call ti_cb_set
    inc dx
    jmp short .side
.out:
    pop si
    pop dx
    pop cx
    pop bx
    ret

; --- ti_cb_text - everything the card SAYS, into the band -------------------
; A FLOW, NOT A SET OF ROWS (SPEC.md 97.4.2). The card has six stats to place
; (TITHE-PLAN 5.2) and four geometries times two faces to place them in, so the
; layout is not decided here at all: each pair is measured, put on the current
; line if it fits and on the next if it does not, and the flow simply STOPS
; when the card runs out of rows. What a geometry shows is then a consequence
; of its own size rather than eight hand-cut cases - and the face key becomes
; a demonstration instead of a preference, because a 6x6 face fits FOUR rows
; where 8x8 fits three and the two stats an 8x8 VGA card drops come back.
;
; THE FIGURE OWNS A COLUMN. The mini unit is ORed into the top-right corner
; over the text's own rows, so the flow's right margin is the card's width
; LESS that column: without it row three ran under the figure and off the
; card, which is what the first composed build put on the glass.
ti_cb_text:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    mov di, ti_cardband
    mov bp, [ti_cbs]
    mov ax, [ti_cardh]              ; rows the face gets, inside the frame
    sub ax, 4
    xor dx, dx
    div word [ti_fh]
    mov [ti_crows], ax
    or ax, ax
    jz .out

    mov ax, [ti_cbw]                ; ...and the column the figure leaves
    sub ax, TI_UNITW + 11
    jnc .w
    mov ax, [ti_fw]
.w:
    mov [ti_tw], ax
    mov word [ti_tx], 3
    mov ax, 2
    add ax, [ti_cpad]
    mov [ti_ty], ax
    mov word [ti_tfull], 0

    cmp word [ti_crows], 2          ; ONE ROW: the pointer picks which (97.4.2)
    jae .name
    cmp word [ti_cx], 0
    je .stats
.name:
    call ti_cb_name
    cmp word [ti_crows], 2          ; ON ONE ROW the name and the costs SHARE
    jb .space                       ; it - a hovered CGA card that spent its
    call ti_cb_nl                   ; only row on the name would answer the
    jmp short .costs                ; one question the hover is asked with
.space:                             ; the one thing already on the card
    mov ax, [ti_tx]
    add ax, [ti_fw]
    mov [ti_tx], ax
.costs:
    mov si, [ti_cardp]              ; what it costs to play...
    mov ah, [si + TI_C_COST]
    mov al, TI_IC_GOLD
    call ti_cb_pair
    mov ax, [ti_cardi]
    and al, 1
    mov ah, al
    mov al, TI_IC_SOUL
    call ti_cb_pair
    cmp word [ti_crows], 2          ; ...on a line of their own, because the
    jb .out                         ; costs stop mattering the moment it is
    call ti_cb_nl                   ; played and the four below never do
.stats:
    call ti_cb_stats
.out:
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; --- ti_cb_nl - the flow's next line, or the end of it ----------------------
ti_cb_nl:
    push ax
    mov word [ti_tx], 3
    push bx
    mov ax, [ti_ty]
    add ax, [ti_fh]
    mov [ti_ty], ax
    add ax, [ti_fh]                 ; the row AFTER this one ends here...
    mov bx, [ti_cardh]              ; ...and the frame's inside ends here
    sub bx, 2
    sub bx, [ti_cpad]
    cmp ax, bx
    jbe .ok
    mov word [ti_tfull], 1
.ok:
    pop bx
    pop ax
    ret

; --- ti_cb_name - the card's name, cut to the column ------------------------
ti_cb_name:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push di
    mov si, [ti_cardp]
    mov si, [si + TI_C_NAME]
    mov ax, [ti_tw]                 ; how many glyphs the column holds
    sub ax, 3
    xor dx, dx
    div word [ti_fw]
    mov cx, ax
    mov di, ti_numbuf
.c:
    or cx, cx
    jz .end
    lodsb
    or al, al
    jz .end
    stosb
    dec cx
    jmp short .c
.end:
    mov byte [di], 0
    pop di
    mov bx, [ti_tx]
    mov dx, [ti_ty]
    mov si, ti_numbuf
    call ti_text
    mov [ti_tx], bx
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; --- ti_cb_pair - one `icon value` pair, flowed. AL = icon, AH = value ------
; It measures before it draws, so a pair that would cross the figure's column
; starts the next line instead - and a pair with no line left is DROPPED
; rather than clipped, which is the difference between a card that shows less
; and one that shows nonsense.
ti_cb_pair:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    cmp word [ti_tfull], 0
    jne .out
    push di                         ; ...THE BAND POINTER, BANKED TWICE. DI is
                                    ; both what ti_text draws into and what
                                    ; stosb builds the string with.
    mov di, ti_numbuf
    stosb                           ; the icon IS a glyph (tifaces.inc)
    mov al, ah
    call ti_u8
    mov byte [di], 0
    pop di
    mov si, ti_numbuf
    call ti_textw                   ; MEASURED FIRST
    mov cx, ax
    mov bx, [ti_tx]
    add bx, cx
    cmp bx, [ti_tw]
    jbe .fits
    cmp word [ti_tx], 3             ; a pair too wide for a WHOLE line would
    je .fits                        ; loop for ever, so it is drawn and cut
    call ti_cb_nl
    cmp word [ti_tfull], 0
    jne .out
.fits:
    mov bx, [ti_tx]
    mov dx, [ti_ty]
    mov si, ti_numbuf
    call ti_text
    add bx, [ti_fw]                 ; ...and a space after it
    mov [ti_tx], bx
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; --- ti_cb_stats - the four that follow it onto the board -------------------
; Wave 1a has no rules behind them, so they are derived from the index exactly
; as ti_cellnum derives its HP - a table would only be a second fiction.
ti_cb_stats:
    push ax
    push si
    mov ax, [ti_cardi]              ; HP, the cell's own fiction
    and al, 7
    add al, 5
    mov ah, al
    mov al, TI_IC_HP
    call ti_cb_pair
    mov si, [ti_cardp]
    mov ah, [si + TI_C_ATK]
    mov al, TI_IC_MELEE             ; stat1
    call ti_cb_pair
    mov si, [ti_cardp]
    mov ah, [si + TI_C_DEF]
    mov al, TI_IC_SHIELD            ; stat2
    call ti_cb_pair
    mov ax, [ti_cardi]              ; POWER, what a kill of it pays
    and al, 3
    inc al
    mov ah, al
    mov al, TI_IC_STAR
    call ti_cb_pair
    pop si
    pop ax
    ret

; --- ti_cb_unit - the mini figure, ORed into the band's right corner --------
; Byte-aligned by construction: a card's width is a multiple of 8 and so is
; TI_UNITW, so this is a byte copy and needs none of ti_glyph's shifter.
ti_cb_unit:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push word [ti_pi]
    mov bx, [ti_cardi]
    add bx, ti_clock
    mov bl, [bx]
    xor bh, bh
    mov [ti_pi], bx
    call ti_unit_build
    call ti_unit_addr
    mov si, di
    mov ax, [ti_cbw]                ; its corner
    sub ax, TI_UNITW
    sub ax, 8
    mov cl, 3
    shr ax, cl
    mov di, ti_cardband
    add di, ax
    mov dx, 2
    add dx, [ti_cpad]
    mov ax, dx
    mul word [ti_cbs]
    add di, ax
    mov dx, [ti_unith]
.row:
    or dx, dx
    jz .done
    push di
    push si
    mov cx, [ti_unitb]
.b:
    lodsb
    or [di], al
    inc di
    loop .b
    pop si
    pop di
    add si, [ti_unitb]
    add di, [ti_cbs]
    dec dx
    jmp short .row
.done:
    pop word [ti_pi]
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

ti_cb_frame2:                       ; the hovered card's inner outline
    push ax
    push bx
    push cx
    push dx
    mov bx, 2
    mov cx, [ti_cbw]
    sub cx, 3
    mov dx, 2
    call ti_cb_hline
    mov dx, [ti_cardh]
    sub dx, 3
    call ti_cb_hline
    mov dx, 2
.side:
    mov ax, [ti_cardh]
    sub ax, 3
    cmp dx, ax
    ja .out
    mov bx, 2
    call ti_cb_set
    mov bx, [ti_cbw]
    sub bx, 3
    call ti_cb_set
    inc dx
    jmp short .side
.out:
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
    add bx, [ti_cpad]
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
