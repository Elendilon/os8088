; =============================================================================
; CLEAR SKIES - the cockpit (SPEC.md 88.9.2)
;
; Drawn ONCE per target when the panel is first painted: the face, the
; instrument windows, their outlines, and a round bezel for the attitude
; indicator - all from shapes, in box coordinates, off a 320-wide layout
; through cs_hscalex, so it is one drawing on three adapters and round on
; each (cs_pasp). A bitmap would have been seven kilobytes a width and
; round on one of them. The readings are then the panel items of 88.9,
; lettered into the windows; the attitude indicator is redrawn on the same
; rate gate as the readings.
; =============================================================================

; -----------------------------------------------------------------------------
; cs_ellipse - an outline of CS_ELSEG segments: centre AX/BX, radii CX/DX
;              (box coordinates), in the current ink, under cs_pclip
; -----------------------------------------------------------------------------
CS_ELSEG equ 24
cs_ellipse:
    mov [cs_elcx], ax
    mov [cs_elcy], bx
    mov [cs_elrx], cx
    mov [cs_elry], dx
    mov word [cs_elang], 0
    call .pt                        ; the first point...
    mov [cs_elx], ax
    mov [cs_ely], bx
    mov cx, CS_ELSEG
.s:
    push cx
    mov ax, 65536 / CS_ELSEG
    add [cs_elang], ax
    call .pt                        ; ...and each next one, joined to the last
    mov cx, ax
    mov dx, bx
    mov ax, [cs_elx]
    mov bx, [cs_ely]
    mov [cs_elx], cx
    mov [cs_ely], dx
    call cs_seg
    pop cx
    loop .s
    ret
.pt:                                ; AX/BX = the point at [cs_elang]
    mov ax, [cs_elang]
    call cs_cos
    mov bx, [cs_elrx]
    MUL14
    add ax, [cs_elcx]
    push ax
    mov ax, [cs_elang]
    call cs_sin
    mov bx, [cs_elry]
    MUL14
    add ax, [cs_elcy]
    mov bx, ax
    pop ax
    ret

; --- the Cessna's cockpit: a record the plane points to (CSP_COCKPIT), so a
;     second aeroplane brings its own panel with its own constants -----------
cs_ck_c172:
    dw .win, 7                      ; CSK_WIN, CSK_NWIN
    dw .items                       ; CSK_ITEMS
    dw 160, 40                      ; CSK_ADCX, CSK_ADCY
    dw 30, 21                       ; CSK_ADRY, CSK_ADHH
    dw 73                           ; CSK_BARW
.win:                               ; x1, y1, x2, y2 at 320 wide, rows below
    dw  13, 13,  75, 25             ;   the view: SPD 000
    dw  13, 39,  91, 51             ;   ALT 00000
    dw 237, 13, 299, 25             ;   HDG 040
    dw 237, 39, 299, 51             ;   THR 100
    dw 237, 57, 313, 64             ;   the throttle bar's slot
    dw  13, 59, 123, 71             ;   ON THE GROUND
    dw   0, 75, 319, 87             ;   the message strip
.items:                             ; the cell each item letters at: x at 320
    dw  16, 16                      ;   wide and the row below the view: SPD
    dw  16, 42                      ;   ALT (a cell is 8 wide on every
    dw 240, 16                      ;   HDG  adapter, so an x is a multiple of
    dw   0,  0                      ;   8 at 320 wide too, or CGA rounds it
    dw 240, 42                      ;   THR  down onto the window's edge)
    dw  16, 62                      ;   the state
    dw 240, 58                      ;   the throttle bar's left end and top row
    dw   0, 78                      ;   the message (centred; the row)

; cs_pcell - BX = an item: out BX = its x at 320 wide, DX = its row below the
;            view, off the plane's cockpit. Clobbers SI
cs_pcell:
    mov si, [cs_plane]
    mov si, [si + CSP_COCKPIT]
    mov si, [si + CSK_ITEMS]
    shl bx, 1
    shl bx, 1
    add si, bx
    mov bx, [si]
    mov dx, [si + 2]
    ret

; -----------------------------------------------------------------------------
; cs_pface - the cockpit, once. Clobbers everything
; -----------------------------------------------------------------------------
cs_pface:
    mov al, CSI_PFACE               ; --- the face -------------------------------
    call cs_setink
    xor ax, ax
    mov bx, [cs_pany]
    mov cx, [cs_vw]
    dec cx
    mov dx, [cs_vh]
    dec dx
    call cs_prect
    mov al, CSI_PBG                 ; --- the windows ----------------------------
    call cs_setink
    mov si, [cs_plane]
    mov si, [si + CSP_COCKPIT]
    mov cx, [si + CSK_NWIN]
    mov si, [si + CSK_WIN]
.w:
    push cx
    push si
    call cs_pwrect
    call cs_prect
    pop si
    pop cx
    add si, 8
    loop .w
    call cs_pclip                   ; --- their outlines, and the panel's top ---
    mov al, CSI_PFG
    call cs_setink
    mov si, [cs_plane]
    mov si, [si + CSP_COCKPIT]
    mov cx, [si + CSK_NWIN]
    mov si, [si + CSK_WIN]
.o:
    push cx
    push si
    call cs_pwrect
    dec ax
    dec bx
    inc cx
    inc dx
    call cs_pbox
    pop si
    pop cx
    add si, 8
    loop .o
    xor ax, ax
    mov bx, [cs_pany]
    mov cx, [cs_vw]
    dec cx
    mov dx, bx
    call cs_seg
    ; --- the attitude indicator: a round bezel round a square window ---------
    mov si, [cs_plane]
    mov si, [si + CSP_COCKPIT]
    mov ax, [si + CSK_ADCX]
    call cs_hscalex
    mov [cs_adcx], ax
    mov ax, [cs_pany]
    add ax, [si + CSK_ADCY]
    mov [cs_adcy], ax
    mov ax, [si + CSK_ADRY]
    mov [cs_adry], ax
    mov ah, al                      ; round on this adapter: rx = ry / aspect
    xor al, al                      ; (AX = ry x 256)
    xor dx, dx
    div word [cs_pasp]
    mov [cs_adrx], ax
    mov ax, [si + CSK_ADHH]
    mov [cs_adhh], ax
    mov bx, ax                      ; the window: 0.7 of the radius each way
    shr ax, 1
    shr bx, 1
    shr bx, 1
    add ax, bx
    shr bx, 1
    sub ax, bx                      ; 0.5 + 0.25 - 0.125 = 0.625, near enough
    mov [cs_adhw], ax
    mov al, CSI_PFG
    call cs_setink
    mov ax, [cs_adcx]
    mov bx, [cs_adcy]
    mov cx, [cs_adrx]
    mov dx, [cs_adry]
    call cs_ellipse
    mov ax, [cs_adcx]
    mov bx, [cs_adcy]
    mov cx, [cs_adrx]
    add cx, cx
    shr cx, 1                       ; (CX = rx again: the two rings are)
    add cx, 3                       ; three columns and one row apart
    mov dx, [cs_adry]
    inc dx
    call cs_ellipse
    call cs_vclip
    jmp cs_adwin                    ; ...and the window, black

; cs_pwrect - SI -> a window row: AX/BX/CX/DX = its box corners
cs_pwrect:
    mov ax, [si]
    call cs_hscalex
    push ax
    mov ax, [si + 4]
    call cs_hscalex
    mov cx, ax
    pop ax
    mov bx, [si + 2]
    add bx, [cs_pany]
    mov dx, [si + 6]
    add dx, [cs_pany]
    ret

; cs_pbox - the outline of the box AX/BX (top left) .. CX/DX, four segments
;           under cs_pclip. Clobbers everything
cs_pbox:
    mov [cs_adx1], ax
    mov [cs_ady1], bx
    mov [cs_adx2], cx
    mov [cs_ady2], dx
    mov dx, bx                      ; the top
    call cs_seg
    mov ax, [cs_adx1]               ; the bottom
    mov bx, [cs_ady2]
    mov cx, [cs_adx2]
    mov dx, bx
    call cs_seg
    mov ax, [cs_adx1]               ; the left
    mov bx, [cs_ady1]
    mov cx, ax
    mov dx, [cs_ady2]
    call cs_seg
    mov ax, [cs_adx2]               ; the right
    mov bx, [cs_ady1]
    mov cx, ax
    mov dx, [cs_ady2]
    jmp cs_seg

; cs_adwin - the attitude indicator's window, black
cs_adwin:
    mov al, CSI_PBG
    call cs_setink
    mov ax, [cs_adcx]
    sub ax, [cs_adhw]
    mov cx, [cs_adcx]
    add cx, [cs_adhw]
    mov bx, [cs_adcy]
    sub bx, [cs_adhh]
    mov dx, [cs_adcy]
    add dx, [cs_adhh]
    jmp cs_prect

; -----------------------------------------------------------------------------
; The attitude indicator (SPEC.md 88.9.2): the horizon as one line in the
; window, sloped by the roll and moved by the pitch, and the aeroplane as two
; bars and a dot that stay put. Keyed by the two angles' top bytes - 256 to
; the turn, 1.4 degrees, which is a pixel and a half at the line's ends -
; and read on the panel's rate gate like the other instruments.
; -----------------------------------------------------------------------------
cs_k_adi:
    mov al, [cs_roll + 1]
    mov ah, [cs_pitch + 1]
    ret

cs_d_adi:
    call cs_adwin                   ; the window over the last line
    ; --- the offset: nose up moves the horizon DOWN, a row per 1.4 degrees --
    mov ax, [cs_pitch]
    mov al, ah
    cbw
    mov [cs_adoff], ax
    ; --- the slope: rows over the half-width, aspect in: t = hw x aspect ----
    mov ax, [cs_adhw]
    mul word [cs_pasp]
    mov al, ah
    mov ah, dl                      ; AX = t, rows for a slope of one
    push ax
    mov ax, [cs_roll]
    call cs_cos
    mov cx, ax                      ; CX = cos, over 0.5 within MAXROLL
    mov ax, [cs_roll]
    call cs_sin
    pop bx                          ; BX = t
    imul bx                         ; DX:AX = t sin
    idiv cx                         ; AX = t tan: the rise over the half-width
    mov [cs_addy], ax
    ; --- the ends: a right bank raises the right end -----------------------
    mov ax, [cs_adcx]
    sub ax, [cs_adhw]
    mov [cs_adx1], ax
    mov ax, [cs_adcx]
    add ax, [cs_adhw]
    mov [cs_adx2], ax
    mov ax, [cs_adcy]
    add ax, [cs_adoff]
    mov bx, ax
    add ax, [cs_addy]
    mov [cs_ady1], ax
    sub bx, [cs_addy]
    mov [cs_ady2], bx
    ; --- clipped to the window's rows: each end past an edge is brought to
    ;     it along the line, one divide ------------------------------------
    mov cx, [cs_adcy]
    sub cx, [cs_adhh]               ; CX = the top row
    mov dx, [cs_adcy]
    add dx, [cs_adhh]               ; DX = the bottom
    mov ax, [cs_ady1]
    mov bx, [cs_ady2]
    cmp ax, cx
    jge .t1
    cmp bx, cx
    jl .none                        ; both above
.t1:
    cmp ax, dx
    jle .t2
    cmp bx, dx
    jg .none                        ; both below
.t2:
    mov si, cs_adx1                 ; end 1 against the other
    mov di, cs_adx2
    call cs_adclip
    mov si, cs_adx2                 ; ...and end 2
    mov di, cs_adx1
    call cs_adclip
    call cs_pclip
    mov al, CSI_PFG
    call cs_setink
    mov ax, [cs_adx1]
    mov bx, [cs_ady1]
    mov cx, [cs_adx2]
    mov dx, [cs_ady2]
    call cs_seg
    jmp short .plane
.none:
    call cs_pclip
    mov al, CSI_PFG
    call cs_setink
.plane:                             ; --- the aeroplane: two bars and a dot ---
    mov bx, [cs_adhw]
    shr bx, 1                       ; the bars: from a quarter to a half of
    mov cx, bx                      ; the half-width, either side
    shr cx, 1
    mov ax, [cs_adcx]
    sub ax, bx
    push cx
    mov cx, [cs_adcx]
    pop dx
    sub cx, dx                      ; CX = cx - hw/4
    mov bx, [cs_adcy]
    mov dx, bx
    call cs_seg
    mov bx, [cs_adhw]
    shr bx, 1
    mov cx, bx
    shr cx, 1
    mov ax, [cs_adcx]
    add ax, cx
    mov cx, [cs_adcx]
    add cx, bx
    mov bx, [cs_adcy]
    mov dx, bx
    call cs_seg
    mov ax, [cs_adcx]               ; the dot
    mov cx, ax
    mov bx, [cs_adcy]
    mov dx, bx
    call cs_seg
    jmp cs_vclip

; cs_adclip - the end at SI (x, then y) brought to the window's row it is
;             past, along the line to the end at DI. CX = the top row, DX =
;             the bottom; both preserved
cs_adclip:
    mov ax, [si + 2]                ; its y
    cmp ax, cx
    jl .to                          ; above: to the top
    cmp ax, dx
    jle .ok
    push cx
    mov cx, dx                      ; below: to the bottom
    call .to
    pop cx
.ok:
    ret
.to:                                ; y -> CX along the line
    push cx
    push dx
    mov ax, cx
    sub ax, [si + 2]                ; AX = the rows to move
    mov bx, [di + 2]
    sub bx, [si + 2]                ; BX = the rows to the other end
    mov cx, [di]
    sub cx, [si]                    ; CX = the columns to it
    imul cx                         ; DX:AX = rows x columns
    idiv bx
    add [si], ax
    pop dx
    pop cx
    mov [si + 2], cx
    ret
