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

; A CARD RECORD, and it holds TITHE-PLAN 5.2's six stats rather than three
; numbers. Two COSTS that matter only while it is a card; HP and POWER, which
; are the same wherever it stands; and TWO PAIRS of variable stats, because
; FRONT AND REAR ARE DIFFERENT ROLES (TITHE-PLAN 5.2) - the same person is a
; shield-and-sword tank in the front column and a pitchfork farmer behind it.
; Each variable stat carries its OWN ICON, the stat being drawn from a list
; (shield, gold, souls, melee, ranged, special) per character rather than
; fixed by the slot it sits in.
TI_C_COST   equ 0                   ; gold, to play it
TI_C_SOUL   equ 1                   ; ...and souls
TI_C_FI1    equ 2                   ; FRONT: stat 1's icon, then its value
TI_C_FV1    equ 3
TI_C_FI2    equ 4                   ; ...and stat 2's
TI_C_FV2    equ 5
TI_C_RI1    equ 6                   ; REAR: the same two, for the back row
TI_C_RV1    equ 7
TI_C_RI2    equ 8
TI_C_RV2    equ 9
TI_C_HP     equ 10
TI_C_PWR    equ 11                  ; the souls a kill of it pays
TI_C_NAME   equ 12
TI_C_ART    equ 14                  ; the art it wears, 0FFh for nobody
TI_C_CARD   equ 15                  ; the engine's card, TR_EMPTY for none
TI_C_FLAGS  equ 16                  ; TI_CF_*
TI_C_COL    equ 17                  ; a board cell's column: 0 FRONT, 1 REAR
TI_C_INST   equ 18                  ; ...and the instance an ORDER names
TI_C_SIZE   equ 20

TI_CF_RANGED equ 1                  ; a shooter: it has a stance to show
TI_CF_SNIPE  equ 2                  ; ...and it is SNIPE

TI_ROW_FRONT equ 0
TI_ROW_REAR  equ 1

; the seven icons, which are glyphs 1..7 of every face (tools/os88titheface.py)
TI_IC_HP    equ 1
TI_IC_GOLD  equ 2
TI_IC_SOUL  equ 3
TI_IC_MELEE equ 4
TI_IC_SHIELD equ 5
TI_IC_BOW   equ 6
TI_IC_STAR  equ 7
TI_IC_SFRONT equ 8                  ; a ranged character's standing order
TI_IC_SNIPE equ 9                   ; (TITHE-PLAN 5.4)

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
    cmp byte [ti_horiz], 0
    je .vert
    call ti_hand_lay
    jmp .out
.vert:
    mov ax, [ti_cardh]              ; a strip row's band is the card
    mov [ti_cbrows], ax
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
; ti_hand_lay - the FULLSCREEN hand (SPEC.md 97.4.12): seven portrait cards
; along the bottom and the COMMIT column after them
; clobbers: AX, DX, flags
;
; EVERY TERM IS A MULTIPLE OF 8. A card's band is blitted with gfx_blit1, so
; its x must be, and the hover INVERT is byte work over the card's columns -
; so the gap between two cards is a whole byte and is never IN a band at all:
; the band is the card, and what lies between two bands is the ground the
; paint put there. That is also why a hovered card RISES rather than widening:
; widening needs a margin inside the band to grow into, and a margin must be a
; byte, which on a 640 screen is a card's worth of the seven.
; -----------------------------------------------------------------------------
ti_hand_lay:
    push bx
    push cx
    mov ax, [ti_ox]
    add ax, 7
    and ax, 0FFF8h
    mov bx, ax
    sub bx, [ti_ox]                 ; the lead-in the snap could not give us
    add ax, 8
    mov [ti_panx], ax               ; card 0, a byte in from the edge
    mov [ti_cardx], ax
    mov ax, [ti_cw_box]             ; the pitch: seven cards and the COMMIT
    sub ax, bx                      ; column in the width, a byte each side
    sub ax, 16 + TI_HCOMMITW
    xor dx, dx
    mov cx, TI_HAND
    div cx
    and ax, 0FFF8h
    cmp ax, TI_HCARDMAX - 8         ; a card no WIDER than it is tall
    jbe .pok
    mov ax, TI_HCARDMAX - 8
.pok:
    mov [ti_cardpitch], ax
    sub ax, 8                       ; ...a byte of ground between two cards
    mov [ti_cardw], ax
    mov ax, [ti_cardpitch]          ; the COMMIT column, after the seventh
    mov cx, TI_HAND
    mul cx
    add ax, [ti_panx]
    mov [ti_cmx], ax
    mov cx, [ti_ox]
    add cx, [ti_cw_box]
    sub cx, 8
    sub cx, ax
    and cx, 0FFF8h
    mov [ti_cmw], cx
    mov ax, [ti_by]                 ; the ROWS: under the board, as tall as
    add ax, [ti_boardh]             ; what is left allows
    add ax, TI_HGAP
    mov [ti_hy], ax
    mov cx, [ti_oy]
    add cx, [ti_ch_box]
    sub cx, ax
    sub cx, TI_HLIFT + TI_HGAP
    cmp cx, TI_HCARDMAX
    jbe .hok
    mov cx, TI_HCARDMAX
.hok:
    mov [ti_cardh], cx
    add cx, TI_HLIFT
    mov [ti_cbrows], cx             ; the band: the card and the room it rises
    mov word [ti_cardn], TI_HAND    ; into
    mov word [ti_cpad], 1
    mov word [ti_cgap], 0
    mov word [ti_unith], TI_UNITHMAX ; the strip's mini units are still built
    mov ax, [ti_cardw]              ; THE PORTRAIT: the board's own figure,
    sub ax, [ti_bw]                 ; centred - which on a 72-wide card is a
    jnc .cen                        ; NIBBLE off a byte, so the offset is
    xor ax, ax                      ; carried as a byte and a shift
.cen:
    shr ax, 1
    mov dx, ax
    and dx, 7
    mov [ti_picsh], dx
    shr ax, 1
    shr ax, 1
    shr ax, 1
    mov [ti_picb], ax
    pop cx
    pop bx
    ret

; -----------------------------------------------------------------------------
; ti_card_pos - AX = hand card AX's band x, BX = its band y
; clobbers: AX, BX, flags
; -----------------------------------------------------------------------------
ti_card_pos:
    push dx
    mul word [ti_cardpitch]
    cmp byte [ti_horiz], 0
    jne .h
    add ax, [ti_by]                 ; the strip steps DOWN...
    mov bx, ax
    mov ax, [ti_panx]
    pop dx
    ret
.h:
    add ax, [ti_panx]               ; ...and the fullscreen hand ACROSS
    mov bx, [ti_hy]
    pop dx
    ret

; -----------------------------------------------------------------------------
; ti_card_geo - the band's geometry for hand card [ti_cardi], whose band x is
; [ti_cposx]: [ti_cl] [ti_cbx] [ti_cbw] [ti_cwd] [ti_cbs] [ti_cbase] [ti_cbbw]
; Preserves every register.
;
; A HOVERED CARD HAS THE RESTING CARD'S SHAPE (SPEC.md 97.4.12.1). It used to
; RISE out of the fullscreen hand and WIDEN across the strip's margins, with
; a second outline inside the first - which made a hover a different picture
; from the card at rest, so every hover change composed two cards from
; nothing: ~57 ms of an 8088 each, and ~150 ms a frame down a sweep of the
; hand. A hovered card is now the resting one NOT INVERTED, so the hover can
; be the cached resting band flipped back (ti_card_fast) instead of a
; composition.
;
; A PORTRAIT'S BAND IS THE CARD, and the card sits at its FOOT: the TI_HLIFT
; rows above it are ground (the room the rise used to take, which the layout
; and the COMMIT column are still cut around). ITS BLIT TAKES THE PAD BYTE:
; `ti_glyph` spills a byte past the card, so the band's stride is the card's
; bytes plus one, and SPEC.md 5.4.2.6's fast path wants the width to BE the
; stride. The pad column is clear - no glyph is placed within 3 pixels of the
; card's edge - and it lands on the byte of black ground between two cards
; (ti_hand_lay), so blitting it costs nothing on the glass and buys ~30% of
; every card's blit.
;
; THE STRIP'S BAND IS THE PANEL'S OWN WIDTH AND THE CARD IS INSET IN IT. A
; card blitted at its own width would leave the 8-pixel margins as the last
; wider draw left them; the MARGINS ARE PART OF THE COMPOSITION, as CLEAR
; bits, which is the only thing that is black on every adapter. That band's
; pad column is past the panel and is not blitted.
; -----------------------------------------------------------------------------
ti_card_geo:
    push ax
    push cx
    cmp byte [ti_horiz], 0
    je .strip
    mov word [ti_cl], 0
    mov ax, [ti_cposx]
    mov [ti_cbx], ax
    mov cx, [ti_cardw]
    mov [ti_cbw], cx
    mov [ti_cwd], cx
    shr cx, 1
    shr cx, 1
    shr cx, 1
    inc cx                          ; ...and ti_glyph's pad byte
    mov [ti_cbs], cx
    mov ax, cx
    shl ax, 1
    shl ax, 1
    shl ax, 1
    mov [ti_cbbw], ax               ; ...which the blit takes too
    mov ax, TI_HLIFT
    mul word [ti_cbs]
    add ax, ti_cardband
    mov [ti_cbase], ax
    jmp short .out
.strip:
    mov word [ti_cbase], ti_cardband
    mov ax, [ti_cardx]
    sub ax, [ti_panx]
    mov [ti_cl], ax
    mov ax, [ti_panx]
    mov [ti_cbx], ax
    mov cx, [ti_pan]
    mov [ti_cbw], cx
    mov [ti_cbbw], cx
    sub cx, [ti_cl]
    sub cx, [ti_cl]
    mov [ti_cwd], cx                ; ...the CARD's own width inside the band
    mov cx, [ti_cbw]
    shr cx, 1
    shr cx, 1
    shr cx, 1
    inc cx                          ; ...the pad byte ti_glyph writes into
    mov [ti_cbs], cx
.out:
    pop cx
    pop ax
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
; -----------------------------------------------------------------------------
; ti_cal_card - microseconds for ONE resting card's COMPOSITION, banked in
; [ti_ccardus]. Preserves every register.
;
; IT EXISTS BECAUSE A COMPOSITION CANNOT BE SEEN ANY OTHER WAY. The picture is
; identical whether the frame takes 3 ms or 40, the wheel still commits, and no
; other row in the suite can tell - so `ti_cb_frame` drew its ~320 pixels one
; at a time through a 16-bit multiply, cost two thirds of a system tick to draw
; a RECTANGLE, and shipped. A whole-frame rate check is too blunt to catch it:
; the defect reads 12.5 frames a second against 15.3 on a metric whose idle is
; 18.6, so a bar loose enough not to flake is loose enough to pass it. This is
; the direct number, and tests/titheframe.py asserts it.
;
; It is `ti_cal_one`'s shape one object along - the same PIT span, the same
; counts-to-microseconds - and it runs once, at layout.
; -----------------------------------------------------------------------------
ti_cal_card:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    push es
    cmp word [ti_cardn], 0
    je .out
    pushf
    cli                             ; the span must not have a tick ISR in it
    call ti_pit
    mov [ti_calc0], ax
    mov word [ti_calconly], 1       ; ...compose, and do NOT put it down
    xor ax, ax
    call ti_card_draw
    mov word [ti_calconly], 0
    call ti_pit
    mov bx, [ti_calc0]
    sub bx, ax                      ; counter 0 counts DOWN
    popf
    mov ax, bx
    xor dx, dx
    mov cx, 8381                    ; one count is 0.8381 us
    mul cx
    mov cx, 10000
    div cx
    mov [ti_ccardus], ax
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
    push word [ti_face]             ; THE PORTRAIT'S FACE IS THE TALL ONE and
    cmp byte [ti_horiz], 0          ; everything else's is not (SPEC.md
    je .face                        ; 97.4.1.1), so it is put back at the end
    mov ax, 1
    call ti_face_set
.face:
    mov ax, [ti_cardi]
    call ti_card_pos                ; AX = the band's x, BX = its top
    mov [ti_cardy], bx
    mov [ti_cposx], ax

    mov si, ti_cards                ; SI -> this card's record
    mov ax, [ti_cardi]
    mov cl, TI_C_SIZE
    mul cl
    add si, ax
    mov [ti_cardp], si

    ; --- hovered? then it is the same card NOT INVERTED -------------------
    mov word [ti_cx], 0
    cmp word [ti_hover], -1
    je .box
    mov cx, [ti_hover]
    cmp cx, [ti_cardi]
    jne .box
    mov word [ti_cx], 1
.box:
    call ti_card_geo

%ifdef TICARDPROF
    pushf
    cli
    call ti_pit
    mov [ti_cp0], ax
%endif
    cmp byte [ti_cfsave], 0         ; A FADING CARD'S STEP puts its bank down
    je .clear                       ; and composes nothing, so the band it
    cmp byte [ti_cfade], 0          ; would clear is not the one it blits
    je .clear                       ; (tirv.inc) - ~3 ms of each of four
    mov ax, [ti_cardi]              ; frames that have the sparks in them
    call ti_rv_played
    jnc .clear
    mov word [ti_cbsrc], ti_cfband
    jmp .blit
.clear:
    mov di, ti_cardband             ; a clean band
    mov ax, [ti_cbs]
    mul word [ti_cbrows]
    mov cx, ax
    push di
    xor al, al
    rep stosb
    pop di

    ; --- A PLAYED CARD is an EMPTY SLOT, and the band is already that -------
    ; unless the reveal is dissolving it out (tirv.inc), which composes the
    ; card as usual and thins it at the blit
    mov ax, [ti_cardi]
    call ti_rv_played
    jnc .live
    cmp byte [ti_cfade], 0
    jne .fading
    jmp .blit
.fading:
    cmp byte [ti_cfsave], 0         ; A FADING CARD IS COMPOSED ONCE: the rest
    je .live                        ; of its steps thin the bank in place and
    mov word [ti_cbsrc], ti_cfband  ; put IT down (tirv.inc) - composing a card
    jmp .blit                       ; is ~22 ms of an 8088, every step
.live:

    ; --- the frame, and the pulse-free second one --------------------------
%ifdef TICARDPROF
%macro TIPROF 1
    call ti_pit
    mov bx, [ti_cp0]
    sub bx, ax
    mov [%1], bx
    call ti_pit
    mov [ti_cp0], ax
%endmacro
%else
%macro TIPROF 1
%endmacro
%endif
    TIPROF ti_pclear
    call ti_cb_frame
    TIPROF ti_pframe
    cmp byte [ti_horiz], 0
    je .strip
    call ti_cb_portrait             ; ...a portrait: name, figure, numbers
    jmp short .composed
.strip:
    call ti_cb_text
    TIPROF ti_ptext
    call ti_cb_unit
.composed:
    TIPROF ti_punit

    ; --- AND THE HOVER INVERTS IN THE BAND, not in the pen -----------------
    ; Which is what makes it INVERT AT ALL on the two adapters the pen does
    ; not reach: a hovered card was distinguished on Hercules and CGA by its
    ; width and by nothing else. The card's columns are byte-aligned by
    ; construction - the panel's x, its width and the margin are all multiples
    ; of 8 - so this is a byte `not` over the card and never over the margins.
    cmp word [ti_cx], 0
    jne .blit                       ; hovered: the picture IS the ink
    call ti_cb_invert
    call ti_card_bank               ; ...and a RESTING card is banked as it
.blit:                              ; stands, for ti_card_fast
    cmp byte [ti_cfade], 0          ; the reveal's dissolve: the card thinned
    je .nofade                      ; to the panel's black a step at a time
    call ti_rv_cardfade
.nofade:
    TIPROF ti_pinv
%ifdef TICARDPROF
    call ti_pit
    mov bx, [ti_cp0]
    sub bx, ax
    mov [ti_ccomp], bx
    popf                            ; ...CLOSED HERE and re-armed below, because
    pushf                           ; the branch under it leaves by another
    cli                             ; door: a `pushf` whose `popf` is on only
    call ti_pit                     ; one path is an unbalanced `ret`, which is
    mov [ti_cp0], ax                ; what tests/unit/t_stkbalance.py exists for
%endif
    cmp word [ti_calconly], 0       ; ti_cal_card wants the COMPOSITION timed
    jne .noblit                     ; and not the arrival that follows it
    mov si, [ti_cbsrc]              ; the card band - or a fading card's bank
    mov ax, [ti_cbx]
    mov bx, [ti_cardy]
    mov cx, [ti_cbbw]
    mov dx, [ti_cbrows]
    mov bp, [ti_cbs]
    call OSAPI_GFX_BLIT1
.noblit:
    mov word [ti_cbsrc], ti_cardband
%ifdef TICARDPROF
    call ti_pit
    mov bx, [ti_cp0]
    sub bx, ax
    mov [ti_cblit], bx
    popf
%endif
    cmp word [ti_calconly], 0
    jne .out

    cmp word [ti_cx], 0             ; the hovered card's box is banked, so the
    je .out                         ; wheel can redraw the UNIT alone
    call ti_hov_bank
.out:
    pop ax                          ; the face the caller had
    call ti_face_set
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
; ti_hov_bank - the hovered card's box, for the wheel's unit step (feature 22)
; Preserves every register. The UNIT's corner is the card's and not the
; band's: the strip's band carries the panel's margins, so its right edge is
; [ti_cl] past the card's (ti_unit_draw puts the unit TI_UNITW + 8 in from it).
; -----------------------------------------------------------------------------
ti_hov_bank:
    push ax
    mov ax, [ti_cbx]
    mov [ti_hovbx], ax
    mov ax, [ti_cl]
    add ax, [ti_cwd]
    mov [ti_hovbw], ax
    mov ax, [ti_cardy]
    mov [ti_hovy], ax
    mov byte [ti_hovage], 0         ; ...and its figure waits (ti_frame)
    pop ax
    ret

; -----------------------------------------------------------------------------
; ti_card_slot - SI = hand card [ti_cardi]'s bank, an offset in the SCRATCH
; part (97.8). Preserves every register bar SI.
; -----------------------------------------------------------------------------
ti_card_slot:
    push ax
    push dx
    mov ax, [ti_cardi]
    mov si, TI_CARDBANDMAX
    mul si
    add ax, TI_S_CARD
    mov si, ax
    pop dx
    pop ax
    ret

; -----------------------------------------------------------------------------
; ti_card_bank - bank the RESTING card just composed in ti_cardband
; Preserves every register.
;
; SPEC.md 97.4.12.1: every resting composition is banked as it stands, so the
; bank is refreshed by whatever redraws a card - a toggle, a deal, a repaint -
; and ti_cvalid is cleared only where a card's CONTENT moves without a redraw
; behind it (tg_vput) and where the art or the layout under it does
; (ti_card_inval).
; -----------------------------------------------------------------------------
ti_card_bank:
    push ax
    push cx
    push dx
    push si
    push di
    push es
    cmp byte [ti_cfade], 0          ; a card being played is not a resting one
    jne .out
    cmp word [ti_calconly], 0       ; ...and ti_cal_card times the COMPOSING,
    jne .out                        ; which tests/titheframe.py holds to a
    call ti_card_slot               ; window - the bank is not part of it
    mov di, si
    call ti_ess                     ; ES = the scratch part
    mov si, ti_cardband
    mov ax, [ti_cbs]
    mul word [ti_cbrows]
    mov cx, ax
    cld
    shr cx, 1
    rep movsw
    adc cx, cx
    rep movsb
    call ti_card_slot               ; ...and its HOVERED twin beside it: the
    mov di, si                      ; same card flipped, once, here - so a
    add di, TI_HAND * TI_CARDBANDMAX ; hover change is two blits and no flip
    call ti_card_flip
    mov si, [ti_cardi]
    mov byte [si + ti_cvalid], 1
.out:
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop ax
    ret

; -----------------------------------------------------------------------------
; ti_card_inval - every card's bank is stale (the art or the layout moved)
; Preserves every register.
; -----------------------------------------------------------------------------
ti_card_inval:
    push ax
    push cx
    push di
    push es
    push ds
    pop es
    cld
    mov di, ti_cvalid
    mov cx, TI_HAND
    xor al, al
    rep stosb
    pop es
    pop di
    pop cx
    pop ax
    ret

; -----------------------------------------------------------------------------
; ti_card_flip - the resting bank at SI (the scratch part) into ES:DI, with
; the CARD's columns flipped on the way: the resting card becomes the hovered
; one (SPEC.md 97.4.12.1). Preserves every register.
;
; ONE PASS AND NOT A COPY AND AN INVERT: each row is the margin copied, the
; card's words `lodsw` / `not` / `stosw`, and the rest copied - with the source
; in DS and the variables reached through CS, which is the package's own
; segment (the near model). It runs where a card is BANKED, which is after a
; ~47 ms composition, and never on a hover.
; -----------------------------------------------------------------------------
ti_card_flip:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push ds
    push es
    mov ax, [ti_cl]                 ; the row's three runs, in bytes
    mov cl, 3
    shr ax, cl
    mov [ti_fmar], ax
    mov bx, [ti_cwd]
    shr bx, cl
    mov [ti_fcard], bx
    mov dx, [ti_cbs]
    sub dx, ax
    sub dx, bx
    mov [ti_frest], dx
    mov ax, [ti_cbase]              ; ...and the band's rows above the card
    sub ax, ti_cardband
    mov [ti_fabove], ax
    mov ax, [ti_cbs]                ; ...and below it
    mul word [ti_cbrows]
    add ax, ti_cardband
    push ax
    mov ax, [ti_cardh]
    mul word [ti_cbs]
    add ax, [ti_cbase]
    pop dx
    sub dx, ax
    mov [ti_fbelow], dx
    mov bx, [ti_cardh]
    push es                         ; DS = the bank's segment, ES = the
    call ti_ess                     ; caller's
    push es
    pop ds
    pop es
    cld
    mov cx, [cs:ti_fabove]
    rep movsb
.row:
    or bx, bx
    jz .below
    mov cx, [cs:ti_fmar]
    rep movsb
    mov dx, [cs:ti_fcard]
    mov cx, dx
    shr cx, 1
    jcxz .odd
.w:
    lodsw
    not ax
    stosw
    loop .w
.odd:
    test dl, 1
    jz .rest
    lodsb
    not al
    stosb
.rest:
    mov cx, [cs:ti_frest]
    rep movsb
    dec bx
    jmp short .row
.below:
    mov cx, [cs:ti_fbelow]
    rep movsb
    pop es
    pop ds
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; ti_card_fast - hand card AX, put down from its BANK when it has one
; Preserves every register. Falls to ti_card_draw for anything the bank does
; not hold: no bank yet, a card being played, an empty slot.
;
; THIS IS WHAT A HOVER CHANGE COSTS NOW (SPEC.md 97.4.12.1). It composed both
; cards from nothing - the frame, the name, the figure, the cost pairs, the
; stats and the invert, ~47 ms of an 8088 for each - so one change was ~131 ms
; and a sweep down the hand ran at a third of the frame rate with the music's
; steps bunched behind it. The card that LOST the hover is its bank blitted as
; it stands; the card that GAINED it is the same bank copied and flipped back,
; since a hovered card is the resting one not inverted. Its figure stands in
; pose 0 until the wheel's feature 22 moves it.
; -----------------------------------------------------------------------------
ti_card_fast:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    push es
    mov bx, ax
    cmp byte [bx + ti_cvalid], 0
    je .slow
    cmp byte [ti_cfade], 0
    jne .slow
    call ti_rv_played
    jc .slow
    mov [ti_cardi], ax
    call ti_card_pos                ; AX = the band's x, BX = its top
    mov [ti_cposx], ax
    mov [ti_cardy], bx
    call ti_card_geo
    call ti_card_slot               ; SI = the bank, in the scratch part
    call ti_ess
    mov ax, [ti_cardi]
    cmp ax, [ti_hover]
    je .hov
    jmp short .put                  ; resting: the bank IS the card
.hov:
    add si, TI_HAND * TI_CARDBANDMAX ; the hovered twin (ti_card_bank)
    call ti_hov_bank
.put:
    mov ax, [ti_cbx]
    mov bx, [ti_cardy]
    mov cx, [ti_cbbw]
    mov dx, [ti_cbrows]
    mov bp, [ti_cbs]
    call OSAPI_GFX_BLIT1
    jmp short .out
.slow:
    call ti_card_draw
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

; --- the band's own primitives: A SPAN AND A LINE, BOTH BYTE-WISE -----------
; They are here and not in os88gfx.inc because a band this small wants no
; clipping and no stride arithmetic beyond one multiply (SPEC.md 5.12's own
; test: a shim would be longer than the body).
;
; A PIXEL AT A TIME THROUGH A MULTIPLY IS WHAT MADE A HOVER STUTTER. The frame
; is ~320 pixels of a card and the second frame another ~270, and a per-pixel
; `mul` plus its own call frame is ~600 cycles: measured with the PIT on the
; machine at 36-44 ms for ONE frame and 38-42 for the second, against a blit
; of the finished card at 4.2 ms. That is two thirds of a system tick to draw
; a rectangle - so the pointer landing on a card cost two frames, which is
; exactly what the field reported. Both bodies below resolve the row ONCE and
; then work in bytes.
;
; ti_cb_span - set pixels [BX, CX] inclusive on band row DX
; Preserves every register.
ti_cb_span:
    push ax
    push bx
    push cx
    push dx
    push di
    cmp dx, [ti_cardh]
    jae .out
    mov ax, [ti_cbw]                ; ...clamped to the band, both ends
    dec ax
    cmp cx, ax
    jbe .rok
    mov cx, ax
.rok:
    cmp bx, cx
    ja .out
    mov [ti_spx0], bx
    mov [ti_spx1], cx

    mov ax, dx                      ; THE ROW, RESOLVED ONCE
    mul word [ti_cbs]
    mov di, [ti_cbase]
    add di, ax
    mov ax, [ti_spx0]
    mov cl, 3
    shr ax, cl
    add di, ax                      ; DI -> the byte holding x0

    mov cx, [ti_spx0]               ; AH = the first byte's mask
    and cx, 7
    mov al, 0FFh
    shr al, cl
    mov ah, al
    mov cx, [ti_spx1]               ; AL = the last byte's
    and cx, 7
    xor cx, 7                       ; ...which is 7 - (x1 & 7)
    mov al, 0FFh
    shl al, cl

    mov bx, [ti_spx1]               ; BX = how many bytes apart they are
    mov cl, 3
    shr bx, cl
    mov cx, [ti_spx0]
    shr cx, 1
    shr cx, 1
    shr cx, 1
    sub bx, cx
    or bx, bx
    jnz .multi
    and al, ah                      ; one byte carries both ends
    or [di], al
    jmp short .out
.multi:
    or [di], ah
    inc di
    dec bx
    jz .last
.mid:
    mov byte [di], 0FFh             ; ...and the middle is whole bytes
    inc di
    dec bx
    jnz .mid
.last:
    or [di], al
.out:
    pop di
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; ti_cb_vline - set pixel BX on band rows [CX, DX] inclusive
; Preserves every register.
ti_cb_vline:
    push ax
    push bx
    push cx
    push dx
    push di
    cmp bx, [ti_cbw]
    jae .out
    mov [ti_spy1], dx
    mov ax, cx                      ; ...the row resolved once here too, and
    mul word [ti_cbs]               ; the rest is a stride add
    mov di, [ti_cbase]
    add di, ax
    mov ax, bx
    push cx
    mov cl, 3
    shr ax, cl
    pop cx
    add di, ax
    and bx, 7
    push cx
    mov cx, bx
    mov al, 080h
    shr al, cl
    pop cx
.row:
    cmp cx, [ti_spy1]
    ja .out
    cmp cx, [ti_cardh]
    jae .out
    or [di], al
    add di, [ti_cbs]
    inc cx
    jmp short .row
.out:
    pop di
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; --- ti_cb_frame - the card's own edges ----------------------------------------
ti_cb_frame:
    push bx
    push cx
    push dx
    mov bx, [ti_cl]
    mov cx, bx
    add cx, [ti_cwd]
    dec cx
    xor dx, dx
    call ti_cb_span                 ; the top...
    mov dx, [ti_cardh]
    dec dx
    call ti_cb_span                 ; ...the foot...
    mov dx, [ti_cardh]
    dec dx
    xor cx, cx
    mov bx, [ti_cl]
    call ti_cb_vline                ; ...and the two uprights
    add bx, [ti_cwd]
    dec bx
    call ti_cb_vline
    pop dx
    pop cx
    pop bx
    ret

; --- ti_cb_invert - flip the CARD's own columns, leaving the margins --------
; The band is composed "the picture is set" and a resting card wants the
; opposite: white paper, black frame, black letters. Flipping it here rather
; than with the pen is what makes the margins work - a clear bit is black on
; every adapter and an ink bit is not (see ti_card_draw) - and it is what
; makes a hovered card invert on the two adapters the pen does not reach.
;
; BYTE WORK AND NOT BIT WORK: the panel's x, its width and the margin are all
; multiples of 8, so the card starts and ends on a byte boundary. A VGA card
; is 14 bytes across 32 rows, which is under half a millisecond against an
; arrival's ~800 us.
ti_cb_invert:
    push ax
    push bx
    push cx
    push dx
    push di
    mov ax, [ti_cl]
    mov cl, 3
    shr ax, cl
    mov di, [ti_cbase]
    add di, ax
    mov bx, [ti_cwd]
    shr bx, cl
    xor dx, dx
.row:
    cmp dx, [ti_cardh]
    jae .out
    push di
    mov cx, bx
    shr cx, 1                       ; ...A WORD AT A TIME, which halves it:
    jcxz .tail                      ; `not` has no `rep` form, so the loop's
.b:                                 ; own overhead is most of its cost
    not word [di]
    inc di
    inc di
    loop .b
.tail:
    test bl, 1
    jz .done
    not byte [di]
.done:
    pop di
    add di, [ti_cbs]
    inc dx
    jmp short .row
.out:
    pop di
    pop dx
    pop cx
    pop bx
    pop ax
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
    mov di, [ti_cbase]
    mov bp, [ti_cbs]
    mov ax, [ti_cardh]              ; rows the face gets, inside the frame
    sub ax, 4
    xor dx, dx
    div word [ti_fh]
    mov [ti_crows], ax
    or ax, ax
    jz .out

    mov ax, [ti_cl]                 ; ...and the column the figure leaves
    add ax, [ti_cwd]
    sub ax, TI_UNITW + 11
    jnc .w
    mov ax, [ti_fw]
.w:
    mov [ti_tw], ax
    mov ax, [ti_cl]
    add ax, 3
    mov [ti_tx], ax
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
    mov si, [ti_cardp]
    mov ah, [si + TI_C_SOUL]
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
    mov ax, [ti_cl]
    add ax, 3
    mov [ti_tx], ax
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
    sub ax, [ti_cl]
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
    or al, al                       ; a ZERO ICON is a pair the card has not
    jz .out                         ; got (tigame.inc's tg_pick)
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
    mov ax, [ti_cl]                 ; a pair too wide for a WHOLE line would
    add ax, 3                       ; loop for ever, so it is drawn and cut
    cmp [ti_tx], ax
    je .fits
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
; THE TWO VARIABLE ONES ARE THE SELECTED ROW'S (SPEC.md 97.4.8). Front and
; rear are different roles, so a card in the hand shows the stats it WOULD have
; where the FRONT/REAR toggle says it is going - which is the question a player
; is answering while looking at it, and the reason the toggle is ONE control
; for the hand rather than a switch on every card.
ti_cb_stats:
    push ax
    push bx
    push si
    mov bx, TI_C_FI1
    cmp word [ti_row], TI_ROW_FRONT
    je .have
    mov bx, TI_C_RI1
.have:
    mov si, [ti_cardp]
    mov ah, [si + TI_C_HP]
    mov al, TI_IC_HP
    or ah, ah                       ; an ORDER has no body to have HP
    jnz .hp
    xor al, al
.hp:
    call ti_cb_pair
    mov si, [ti_cardp]
    add si, bx
    mov ax, [si]                    ; AL = stat 1's icon, AH = its value
    call ti_cb_pair
    mov si, [ti_cardp]
    add si, bx
    mov ax, [si + 2]                ; ...and stat 2's
    call ti_cb_pair
    mov si, [ti_cardp]
    mov ah, [si + TI_C_PWR]
    mov al, TI_IC_SOUL              ; POWER is what a kill of it PAYS, so it is
    cmp byte [si + TI_C_HP], 0      ; (nothing to kill, on an order)
    jne .pw
    xor al, al
.pw:
    call ti_cb_pair                 ; the soul and not the star - the star is a
    pop si                          ; special ABILITY, which is one of the
    pop bx                          ; things a variable stat can BE
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
    xor bx, bx                      ; A RESTING CARD'S UNIT STANDS IN POSE 0.
    cmp word [ti_cx], 0             ; Only the hovered card animates, on the
    je .pose                        ; HAND FEATURE's clock - the one feature
    mov bl, [ti_clock + TI_CELLS]   ; 22 steps and draws from (97.4.12). It
    xor bh, bh                      ; read ti_clock[card], a BOARD CELL's, so
.pose:                              ; a repaint drew a pose the wheel had not
    mov [ti_pi], bx
    mov ax, [ti_cardi]              ; ...and the character this card plays
    call ti_ck_card                 ; (SPEC.md 97.4.9)
    ; ...AND IT IS NOT REBUILT HERE. Every pose is composed once at art-build
    ; time (ti_art_build), and ti_unit_build CLEARS TI_UNITMAX bytes - the
    ; worst case over every geometry - where a live band is unitb * unith. On
    ; the tallest card that is the same number; on every other one the clear
    ; runs into the NEXT pose's band, so rebuilding pose N at draw time blanked
    ; the top of pose N+1 and the card's figure went to pieces as it cycled.
    call ti_unit_addr
    mov si, di
    mov ax, [ti_cl]                 ; its corner
    add ax, [ti_cwd]
    sub ax, TI_UNITW
    sub ax, 8
    mov cl, 3
    shr ax, cl
    mov di, [ti_cbase]
    add di, ax
    mov dx, 2
    add dx, [ti_cpad]
    mov ax, dx
    mul word [ti_cbs]
    add di, ax
    mov dx, [ti_unith]
    push es                         ; THE CACHE IS THE SCRATCH PART'S (97.8):
    call ti_ess                     ; read through ES, into our card band
.row:
    or dx, dx
    jz .done
    push di
    push si
    mov cx, [ti_unitb]
.b:
    mov al, [es:si]
    inc si
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
    pop es
    pop word [ti_pi]
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

;
; --- ti_cb_portrait - a FULLSCREEN card's contents (SPEC.md 97.4.12) --------
; THE PICTURE IS THE LARGER HALF. The strip's card is a line of text with a
; 24-pixel figure in its corner; a portrait has the rows for the character at
; the BOARD's own size, so it is the name, then the figure, then what it costs
; and the four stats in the flow the strip already uses - in the tall face.
ti_cb_portrait:
    push ax
    push bx
    push di
    push bp
    mov di, [ti_cbase]
    mov bp, [ti_cbs]
    mov ax, [ti_cwd]
    sub ax, 3
    mov [ti_tw], ax
    mov word [ti_tx], 3
    mov ax, 2
    add ax, [ti_cpad]
    mov [ti_ty], ax
    mov word [ti_tfull], 0
    call ti_cb_name
    mov ax, [ti_ty]                 ; the figure, under the name - a ROW
    add ax, [ti_fh]                 ; apart and not two, which is the row a
    inc ax                          ; Hercules card needs for its last stats
    mov [ti_picy], ax
    push word [ti_pi]
    xor bx, bx                      ; a resting card stands in pose 0 and the
    cmp word [ti_cx], 0             ; hovered one on the hand feature's clock,
    je .pose                        ; which is the one ti_pic_anim draws from
    mov bl, [ti_clock + TI_CELLS]
    xor bh, bh
.pose:
    mov [ti_pi], bx
    call ti_cb_pic
    pop word [ti_pi]
    add ax, [ti_bh]                 ; ...and the numbers under the figure
    inc ax
    mov [ti_ty], ax
    mov word [ti_tx], 3
    add ax, [ti_fh]                 ; a card too short for even this line
    mov bx, [ti_cardh]              ; says nothing rather than something cut
    sub bx, 2
    sub bx, [ti_cpad]
    cmp ax, bx
    jbe .costs
    mov word [ti_tfull], 1
.costs:
    push si
    mov si, [ti_cardp]
    mov ah, [si + TI_C_COST]
    mov al, TI_IC_GOLD
    call ti_cb_pair
    mov si, [ti_cardp]
    mov ah, [si + TI_C_SOUL]
    mov al, TI_IC_SOUL
    call ti_cb_pair
    pop si
    cmp word [ti_tfull], 0
    jne .out
    call ti_cb_nl
    call ti_cb_stats
.out:
    pop bp
    pop di
    pop bx
    pop ax
    ret

; --- ti_cb_pic - OR the portrait's figure into the band ---------------------
; in:  [ti_cardi], [ti_pi] = the pose, [ti_picy] = its first card row
; Preserves every register.
;
; THE FIGURE IS STORED AT THE CARD'S OWN OFFSET. A 64-wide figure on a 72-wide
; card is centred four pixels off a byte, and this used to take the half-byte
; here - a shift by CL both ways for every byte, which an 8088 prices at 8 + 4
; clocks a bit: 14 ms of VGA figure, in every card composition and in every
; step of the hovered card's animation. ti_art_one shifts each pose ONCE
; into a row a byte wider (ti_fig_shift), so this is a plain OR of bs + 1
; bytes a row (SPEC.md 97.4.12.1).
ti_cb_pic:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    push ds
    push es
    push ds
    pop es                          ; the band is the package's...
    mov ax, [ti_cardi]
    call ti_ck_card
    cmp word [ti_ck], 0FFh          ; an ORDER has no figure
    jne .fig
    jmp .out
.fig:
    mov ax, [ti_uk]
    mov dx, TI_POSES
    mul dx
    add ax, [ti_pi]
    mov cx, ax
    mov ax, [ti_bs]
    inc ax
    mov dx, ax                      ; DX = a stored row
    mul word [ti_bh]
    mul cx
    mov si, ax                      ; ...the figure the claim's
    mov ax, [ti_picy]
    mul word [ti_cbs]
    add ax, [ti_cbase]
    add ax, [ti_picb]
    mov di, ax
    mov bx, [ti_bh]
    mov bp, [ti_cbs]
    mov ax, [ti_bs]
    inc ax
    mov dx, ax
    mov ds, [ti_fseg]
.row:
    or bx, bx
    jz .out
    mov cx, dx
.b:
    lodsb
    or [es:di], al
    inc di
    loop .b
    sub di, dx
    add di, bp
    dec bx
    jmp short .row
.out:
    pop es
    pop ds
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; --- ti_fig_shift - pose at ES:DI, stored rows [ti_fa_stride] wide, moved
; [ti_picsh] bits right in place: the half-byte ti_cb_pic used to take on
; every draw, taken once. Preserves every register. A shift of 8 is zero on
; an 8086 (the count is not masked), so an aligned card needs no second body.
ti_fig_shift:
    push ax
    push bx
    push cx
    push dx
    push di
    mov cl, [ti_picsh]
    mov ch, 8
    sub ch, cl
    mov bx, [ti_bh]
.row:
    or bx, bx
    jz .out
    push di
    mov dx, [ti_bs]                 ; from the row's LAST byte back to its
    add di, dx                      ; second: each takes its own bits and
.b:                                 ; the left neighbour's spill
    mov al, [es:di]
    shr al, cl
    mov ah, [es:di - 1]
    xchg cl, ch
    shl ah, cl
    xchg cl, ch
    or al, ah
    mov [es:di], al
    dec di
    dec dx
    jnz .b
    mov al, [es:di]                 ; ...and the first
    shr al, cl
    mov [es:di], al
    pop di
    add di, [ti_fa_stride]
    dec bx
    jmp short .row
.out:
    pop di
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; --- ti_pic_anim - the hovered portrait's next pose, and nothing else -------
; in:  [ti_hover] a card, [ti_pi] = the pose
; Preserves every register.
;
; THE WHEEL'S STEP FOR THE 21st FEATURE. The strip redraws the mini unit alone
; because it sits in a corner of its own; a portrait's figure crosses the
; card's two uprights, so this recomposes EXACTLY those rows - cleared, the
; uprights put back, the figure ORed over - and puts down the figure's rows
; and not the card: a composition of the whole card is ~22 ms of an 8088 and
; this is one band of the board's own size. The card sits at its band's FOOT,
; hovered or not (ti_card_geo), so the rows are TI_HLIFT down the band.
ti_pic_anim:
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
    mov ax, [ti_hover]
    mov [ti_cardi], ax
    call ti_card_pos                ; AX = x, BX = the band's top
    mov [ti_cposx], ax
    mov [ti_cardy], bx
    call ti_card_geo
    mov ax, [ti_picy]               ; the figure's rows, cleared
    mul word [ti_cbs]
    add ax, [ti_cbase]
    mov di, ax
    mov ax, [ti_cbs]
    mul word [ti_bh]
    mov cx, ax
    xor al, al
    rep stosb
    mov cx, [ti_picy]               ; ...the uprights through them
    mov dx, cx
    add dx, [ti_bh]
    dec dx
    xor bx, bx
    call ti_cb_vline
    mov bx, [ti_cwd]
    dec bx
    call ti_cb_vline
    call ti_cb_pic                  ; ...and the figure over them
    mov ax, [ti_picy]
    mul word [ti_cbs]
    add ax, [ti_cbase]
    mov si, ax
    mov ax, [ti_cbx]
    mov bx, [ti_cardy]
    add bx, TI_HLIFT
    add bx, [ti_picy]
    mov cx, [ti_cbbw]
    mov dx, [ti_bh]
    mov bp, [ti_cbs]
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
; ti_units_build - every hand card's art, four poses each (SPEC.md 97.4.9,
; 97.4.12): the fullscreen hand's PORTRAIT figures, or the strip's mini units
; - whichever the layout draws, and not both
; Preserves every register.
;
; THE CARD'S OWN ANIMATION (TITHE-PLAN 3.3), and the LAYER MODEL's clearest
; demonstration: FRONT/REAR decides which pair of stats a card shows (97.4.8),
; and it decides which ITEM the figure holds too, so flipping the toggle turns
; the pikeman's sword into a pitchfork on the card in the hand. It built BOTH
; stores on every toggle - 200 ms of strip units a fullscreen hand never
; reads, beside its own 700 ms of portraits - and a relayout builds whichever
; the new layout wants anyway. A toggle does not come here at all now: the
; worker rebuilds it a pose at a time (ti_row_step, SPEC.md 97.4.8.2).
; -----------------------------------------------------------------------------
ti_units_build:
    call ti_card_inval              ; the art under every bank moves
    mov byte [ti_rowst], 0          ; ...and a toggle's rebuild is overtaken
    push ax
    push bx
    xor ax, ax                      ; ONE PER HAND SLOT (tigame.inc): the card
.card:                              ; in the slot, whoever it is this round
    cmp ax, TI_HAND
    jae .done
    xor bx, bx
.pose:
    cmp bx, TI_POSES
    jae .next
    call tm_run                     ; the music a pose at a time
    call ti_art_one
    inc bx
    jmp short .pose
.next:
    inc ax
    jmp short .card
.done:
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; ti_art_one - hand card AX's pose BX into its store: the PORTRAIT figure on
; the fullscreen hand (the claim ti_fseg, at the card's nibble - ti_fig_shift),
; the strip's mini UNIT otherwise (the scratch part, TI_S_UNIT)
; Preserves every register.
;
; The board's own records on black, through ti_char_put, with the item the
; FRONT/REAR toggle names. A unit is a surface of its own - 24 wide where the
; board's band is 64 - and `TI_CHAR_BG` is where its records start.
; -----------------------------------------------------------------------------
ti_art_one:
    push ax
    push bx
    push cx
    push dx
    push di
    push es
    push word [ti_pi]
    push word [ti_ck]
    push word [ti_uk]
    cld
    mov [ti_pi], bx
    mov [ti_cfr], bx
    call ti_ck_card                 ; [ti_uk] = the hand slot's store
    mov word [ti_cdx], 0
    mov word [ti_cdy], 0
    mov byte [ti_fa_mir], 0
    mov ax, [ti_row]
    mov [ti_cst], ax
    cmp byte [ti_horiz], 0
    je .unit
    mov ax, [ti_bs]                 ; A PORTRAIT ROW IS A BYTE WIDER than the
    mov [ti_fa_wb], ax              ; board's band, because the figure is
    inc ax                          ; STORED at the card's own nibble
    mov [ti_fa_stride], ax
    mul word [ti_bh]
    mov [ti_uslot], ax
    mov ax, [ti_bh]
    mov [ti_fa_h], ax
    mov [ti_cbh], ax
    mov ax, [ti_gidx]               ; the BOARD's surface, not the unit's
    mov [ti_csurf], ax
    mov ax, [ti_uk]
    mov cx, TI_POSES
    mul cx
    add ax, [ti_pi]
    mul word [ti_uslot]
    mov di, ax
    mov es, [ti_fseg]
    jmp short .put
.unit:
    mov ax, [ti_unitb]              ; the slot's own pitch, and the window
    mov [ti_fa_stride], ax
    mov [ti_fa_wb], ax
    mul word [ti_unith]
    mov [ti_uslot], ax
    mov ax, [ti_unith]
    mov [ti_fa_h], ax
    mov [ti_cbh], ax
    mov ax, TI_CHAR_BG
    add ax, [ti_gidx]
    mov [ti_csurf], ax
    call ti_ess                     ; the units are the scratch part's
    call ti_unit_addr
.put:
    push di                         ; the slot, cleared to the card's black,
    mov cx, [ti_uslot]              ; then the character
    xor al, al
    rep stosb
    pop di
    call ti_char_put                ; (nothing, for an order or an empty slot)
    cmp byte [ti_horiz], 0
    je .out
    call ti_fig_shift
.out:
    pop word [ti_uk]
    pop word [ti_ck]
    pop word [ti_pi]
    pop es
    pop di
    pop dx
    pop cx
    pop bx
    pop ax
    ret

ti_unit_addr:
    push ax
    push dx
    mov ax, [ti_uk]                 ; the hand SLOT's cache, not the art's -
                                    ; in the SCRATCH part (97.8), so DI is an
                                    ; offset there and ES must be ti_ess's
    mov dx, TI_POSES
    mul dx
    add ax, [ti_pi]
    mov dx, TI_UNITMAX
    mul dx
    mov di, TI_S_UNIT
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
    cmp byte [ti_horiz], 0          ; a PORTRAIT's figure is not a corner unit
    je .strip
    jmp ti_pic_anim
.strip:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    push es
    call ti_ess                     ; ES:SI = the cache, in the scratch part
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

    cmp byte [ti_horiz], 0
    je .vert
    call ti_commit_col
    jmp .out
.vert:
    mov ax, [ti_cardn]
    call ti_card_pos
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
    mov si, [tg_lbl]                ; PLAN, or HAND (tigame.inc)
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

; ti_commit_col - the fullscreen hand's COMMIT column (SPEC.md 97.4.12): UNDO
; above COMMIT, each a framed box, level with the cards and not risen
; clobbers: AX, BX, CX, DX, SI
ti_commit_col:
    mov al, CBLACK                  ; the column's ground, risen rows and all
    call OSAPI_SET_COLOR
    mov ax, [ti_cmx]
    mov bx, [ti_hy]
    mov cx, ax
    add cx, [ti_cmw]
    dec cx
    mov dx, bx
    add dx, [ti_cbrows]
    dec dx
    call OSAPI_GFX_FILL
    mov al, CWHITE
    call OSAPI_SET_COLOR
    mov bx, [ti_hy]                 ; UNDO, a quarter of the card's height
    add bx, TI_HLIFT
    mov dx, [ti_cardh]
    shr dx, 1
    shr dx, 1
    add dx, bx
    mov [ti_cmsplit], dx
    mov ax, [ti_cmx]
    mov cx, ax
    add cx, [ti_cmw]
    dec cx
    call OSAPI_GFX_FRAME
    mov bx, [ti_cmsplit]            ; ...and COMMIT under it, to the foot
    add bx, 4
    mov dx, [ti_hy]
    add dx, TI_HLIFT
    add dx, [ti_cardh]
    dec dx
    call OSAPI_GFX_FRAME
    mov cx, [ti_cmw]                ; the labels, centred: UNDO is four cells
    sub cx, 32
    shr cx, 1
    add cx, [ti_cmx]
    mov dx, [ti_hy]
    add dx, TI_HLIFT + 4
    mov si, [tg_lbl]                ; PLAN, or HAND (tigame.inc)
    mov ax, (CBLACK << 8) | CWHITE
    call OSAPI_FONT_RUN
    mov cx, [ti_cmw]                ; ...and COMMIT six
    sub cx, 48
    shr cx, 1
    add cx, [ti_cmx]
    mov dx, [ti_cmsplit]
    add dx, 8
    mov si, ti_s_commit
    mov ax, (CBLACK << 8) | CWHITE
    call OSAPI_FONT_RUN
    ret

; -----------------------------------------------------------------------------
; ti_panel - the whole panel, with the board
; Preserves every register.
; -----------------------------------------------------------------------------
ti_panel:
    push ax
    push cx
    cmp byte [tg_list], 0           ; THE PLAN where the hand was (tigame.inc)
    je .hand
    call tg_list_show
    jmp short .done
.hand:
    xor ax, ax
.row:
    cmp ax, [ti_cardn]
    jae .done
    push ax
    call ti_card_draw
    call tm_run                     ; the music a card at a time
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
    cmp byte [tg_list], 0           ; the plan list has no cards to hover
    jne .nocard
    cmp byte [ti_horiz], 0          ; the fullscreen hand asks the click's own
    je .strip                       ; box, which knows the risen card
    call ti_card_hit
    cmp ax, -1
    je .have
    call ti_rv_played
    jnc .have
    jmp short .nocard
.strip:
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
    jae .nocard
    call ti_rv_played               ; a PLAYED card is an empty slot, and
    jnc .have                       ; hovering one names nothing
.nocard:
    mov ax, -1
.have:
    ; ...AND THE BOARD IS ASKED THE SAME QUESTION (SPEC.md 97.4.8). A character
    ; on the board has the same special ability the card in the hand has, so
    ; the HUD's status line answers for either - and a hover that only worked
    ; on the panel would say so by going blank the moment the pointer reached
    ; the thing it was about. It is a LINEAR WALK of twenty cells and not a
    ; reverse of the shear: `ti_cellpos` is the only place that knows where a
    ; cell is, and inverting it in a second place is how the two get to
    ; disagree.
    push ax
    call ti_cell_hit
    mov [ti_hovc2], ax
    pop ax
    cmp ax, [ti_hover]
    jne .chg
    mov bx, [ti_hovc2]
    cmp bx, [ti_hovc]
    je .same
    mov [ti_hovc], bx               ; the BOARD's hover moved and the panel's
    pop dx                          ; did not: the HUD is the only thing that
    pop cx                          ; changed, and ti_hovold stays -1 so no
    pop bx                          ; card is redrawn for it
    pop ax
    mov word [ti_hovold], -1
    stc
    ret
.chg:
    mov bx, [ti_hovc2]
    mov [ti_hovc], bx
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

; -----------------------------------------------------------------------------
; ti_card_hit - AX = the hand card at (CX, DX), or -1: the same box the hover
; test uses, so the card a click plays is the card it lit.
; Preserves every register bar AX.
; -----------------------------------------------------------------------------
ti_card_hit:
    push bx
    push dx
    mov ax, -1
    cmp byte [ti_horiz], 0
    je .vert
    push cx                         ; ACROSS: which pitch, then the gap, then
    sub cx, [ti_panx]               ; the band's rows - the risen card's too,
    jb .hno                         ; so the pointer that lifted it stays on it
    mov ax, cx
    xor dx, dx
    div word [ti_cardpitch]
    cmp ax, [ti_cardn]
    jae .hmiss
    cmp dx, [ti_cardw]
    jae .hmiss
    pop cx
    pop dx
    push dx
    sub dx, [ti_hy]
    jb .hmiss2
    cmp dx, [ti_cbrows]
    jb .out
.hmiss2:
    mov ax, -1
    jmp short .out
.hmiss:
    mov ax, -1
.hno:
    pop cx
    jmp short .out
.vert:
    cmp cx, [ti_cardx]
    jb .out
    mov bx, [ti_cardx]
    add bx, [ti_cardw]
    cmp cx, bx
    jae .out
    sub dx, [ti_by]
    jb .out
    mov ax, dx
    xor dx, dx
    div word [ti_cardpitch]
    cmp ax, [ti_cardn]
    jb .have
    mov ax, -1
    jmp short .out
.have:
    cmp dx, [ti_cardh]              ; ...and not the gap below it
    jb .out
    mov ax, -1
.out:
    pop dx
    pop bx
    ret

; -----------------------------------------------------------------------------
; ti_cell_hit - AX = the board cell at (CX, DX), or -1
; Preserves every register bar AX.
; -----------------------------------------------------------------------------
ti_cell_hit:
    cmp cx, [ti_chx]                ; THE SAME POINT ASKED AGAIN is the same
    jne .walk                       ; answer until the layout moves: the walk
    cmp dx, [ti_chy]                ; is twenty ti_cellpos and ran every frame
    jne .walk                       ; from ti_hover_ck, parked pointer or not.
    mov ax, [ti_nlay]               ; Both callers hold the gfx lock, so the
    cmp ax, [ti_chl]                ; four words cannot be read half-written
    jne .walk
    mov ax, [ti_chr]
    ret
.walk:
    push bx
    push cx
    push dx
    push si
    push di
    push word [ti_ci]
    mov word [ti_ci], 0
    mov ax, [ti_bx]                 ; ...AND A POINT OFF THE BOARD'S BOX is on
    cmp cx, ax                      ; no cell: the box is four cells across
    jb .none                        ; and five plus the shear down, so every
    add ax, [ti_boardw]             ; cell is inside it (tilay.inc). A sweep
    cmp cx, ax                      ; of the HAND is below it, and was twenty
    jae .none                       ; ti_cellpos a frame for no answer
    mov ax, [ti_by]
    cmp dx, ax
    jb .none
    add ax, [ti_boardh]
    cmp dx, ax
    jae .none
.n:
    mov ax, [ti_ci]
    cmp ax, TI_CELLS
    jae .none
    call ti_cell_xy                 ; AX = the cell's x, BX = its y
    cmp cx, ax
    jb .next
    mov si, ax
    add si, [ti_cw]
    cmp cx, si
    jae .next
    cmp dx, bx
    jb .next
    mov si, bx
    add si, [ti_ch]
    cmp dx, si
    jae .next
    mov ax, [ti_ci]
    jmp short .out
.next:
    inc word [ti_ci]
    jmp short .n
.none:
    mov ax, -1
.out:
    mov [ti_chx], cx
    mov [ti_chy], dx
    mov [ti_chr], ax
    mov bx, [ti_nlay]
    mov [ti_chl], bx
    pop word [ti_ci]
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    ret
