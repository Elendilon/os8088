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
    dw 0, 0                         ; CSK_DECO, CSK_NDECO: a trainer's panel
                                    ; is the instruments and nothing else
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
    dw   0,  0                      ;   no variometer: an aeroplane with an
                                    ;   engine does not carry one (88.7.6)

; --- the PITTS SPECIAL's (SPEC.md 88.9.3): the same eight readings, put
;     where an aerobatic biplane's are rather than in two tidy columns - the
;     altimeter left of centre where the pilot's eye falls, the speed above
;     it, heading and throttle down the right, and the attitude indicator off
;     the centreline. The four dials and the two magneto switches are
;     DECORATION: they are drawn once with the face and nothing ever reads
;     them, which is what a real panel is mostly made of ---------------------
cs_ck_pitts:
    dw .win, 7                      ; CSK_WIN, CSK_NWIN
    dw .items                       ; CSK_ITEMS
    dw 175, 38                      ; CSK_ADCX, CSK_ADCY: off centre, right
    dw 22, 16                       ; CSK_ADRY, CSK_ADHH
    dw 73                           ; CSK_BARW
    dw .deco, 6                     ; CSK_DECO, CSK_NDECO
.win:                               ; x1, y1, x2, y2 at 320 wide, rows below
    dw  13,  6,  75, 18             ;   SPD 000, high on the left
    dw  13, 30,  91, 42             ;   ALT 00000, LEFT OF CENTRE
    dw 237, 44, 299, 56             ;   HDG 040, low right
    dw 237,  6, 299, 18             ;   THR 100, high right
    dw 237, 24, 313, 31             ;   the throttle bar's slot
    dw  13, 58, 123, 70             ;   ON THE GROUND
    dw   0, 75, 319, 87             ;   the message strip
.items:                             ; the cell each item letters at (x is a
    dw  16,  9                      ;   SPD  multiple of 8 at 320 wide, or CGA
    dw  16, 33                      ;   ALT  rounds it down onto the window's
    dw 240, 47                      ;   HDG  edge)
    dw   0,  0                      ;   (the attitude indicator draws itself)
    dw 240,  9                      ;   THR
    dw  16, 61                      ;   the state
    dw 240, 25                      ;   the throttle bar's left end and top row
    dw   0, 78                      ;   the message (centred; the row)
    dw   0,  0                      ;   no variometer (88.7.6)
.deco:                              ; kind, x, y, radius in rows, argument
    dw CSDK_DIAL,   106, 20, 15, 8000    ; the tachometer, showing cruise
    dw CSDK_DIAL,   106, 56, 13, 54000   ; oil pressure, up in the green
    dw CSDK_DIAL,   216, 20, 13, 29000   ; fuel, a little under half
    dw CSDK_DIAL,   216, 56, 15, 45000   ; the G meter, parked at 1
    dw CSDK_SWITCH, 143, 68,  5, 1       ; the magnetos: left on...
    dw CSDK_SWITCH, 157, 68,  5, 1       ; ...and right

; --- the Magister's: a JET's panel (SPEC.md 88.7.5). The attitude indicator
;     is the centrepiece and the biggest of the three, because at 190 metres a
;     second it is the instrument you fly on; there is no tachometer, and the
;     dial under the left hand is the ENGINE, which visibly lags the throttle
;     - the spool given something to show, so the mechanic is legible and not
;     only felt -------------------------------------------------------------
cs_ck_fouga:
    dw .win, 7                      ; CSK_WIN, CSK_NWIN
    dw .items                       ; CSK_ITEMS
    dw 160, 36                      ; CSK_ADCX, CSK_ADCY: centred, and BIG
    dw 33, 24                       ; CSK_ADRY, CSK_ADHH
    dw 73                           ; CSK_BARW
    dw .deco, 4                     ; CSK_DECO, CSK_NDECO
.win:                               ; x1, y1, x2, y2 at 320 wide, rows below
    dw  13,  6,  75, 18             ;   SPD 000, top left: the one you watch
    dw  13, 24,  91, 36             ;   ALT 00000, under it
    dw 237,  6, 299, 18             ;   HDG 040, top right
    dw 237, 24, 299, 36             ;   THR 100
    dw 237, 42, 313, 49             ;   the throttle bar's slot
    dw  13, 58, 123, 70             ;   ON THE GROUND
    dw   0, 75, 319, 87             ;   the message strip
.items:
    dw  16,  9                      ;   SPD
    dw  16, 27                      ;   ALT
    dw 240,  9                      ;   HDG
    dw   0,  0                      ;   (the attitude indicator draws itself)
    dw 240, 27                      ;   THR
    dw  16, 61                      ;   the state
    dw 240, 43                      ;   the throttle bar
    dw   0, 78                      ;   the message
    dw   0,  0                      ;   no variometer (88.7.6)
.deco:                              ; kind, x, y, radius in rows, argument
    dw CSDK_DIAL,    58, 46, 14, 20000   ; % RPM - THE SPOOL, which is why it
                                         ; is under the throttle hand
    dw CSDK_DIAL,   262, 62, 12, 40000   ; the jet-pipe temperature
    dw CSDK_SWITCH, 143, 68,  5, 1       ; the two igniters
    dw CSDK_SWITCH, 157, 68,  5, 1

; --- the Bijave's: A GLIDER'S PANEL (SPEC.md 88.7.6). There is no throttle,
;     so the window and the bar that would show one are simply not in the
;     list - a THR 000 that can never be anything else reads as a defect -
;     and what stands where they were is the VARIOMETER, the one instrument
;     a sailplane is actually flown on. The airbrake lever is the switch ----
cs_ck_bijave:
    dw .win, 7                      ; CSK_WIN, CSK_NWIN
    dw .items                       ; CSK_ITEMS
    dw 160, 38                      ; CSK_ADCX, CSK_ADCY
    dw 28, 20                       ; CSK_ADRY, CSK_ADHH
    dw 73                           ; CSK_BARW: unused - no bar is drawn
    dw .deco, 3                     ; CSK_DECO, CSK_NDECO
.win:                               ; x1, y1, x2, y2 at 320 wide, rows below
    dw  13,  8,  75, 20             ;   SPD 000
    dw  13, 30,  91, 42             ;   ALT 00000
    dw 237,  8, 299, 20             ;   HDG 040
    dw 237, 30, 299, 42             ;   UP 015 - THE VARIOMETER, where a
                                    ;   powered aeroplane keeps its throttle
    dw  13, 58, 123, 70             ;   ON THE GROUND
    dw   0, 75, 319, 87             ;   the message strip
    dw 237, 48, 299, 60             ;   (the vario's own window, second half)
.items:
    dw  16, 11                      ;   SPD
    dw  16, 33                      ;   ALT
    dw 240, 11                      ;   HDG
    dw   0,  0                      ;   (the attitude indicator draws itself)
    dw   0,  0                      ;   NO THROTTLE
    dw  16, 61                      ;   the state
    dw   0,  0                      ;   ...and no throttle bar either
    dw   0, 78                      ;   the message
    dw 240, 33                      ;   THE VARIOMETER
.deco:                              ; kind, x, y, radius in rows, argument
    dw CSDK_DIAL,    58, 46, 15, 16384   ; the vario's own face, needle level
    dw CSDK_DIAL,   262, 66, 11, 49000   ; the total-energy compensator
    dw CSDK_SWITCH, 150, 68,  6, 0       ; the airbrakes: IN

; --- the A5's: A MODERN LSA'S (SPEC.md 88.7.7). One wide glass panel rather
;     than a scatter of round dials, so the readings sit in a single block
;     left of a big attitude indicator - and it carries the VARIOMETER too,
;     which a light amphibian really does. The switch pair is the WATER
;     RUDDER, the one control that only means something on this aeroplane --
cs_ck_a5:
    dw .win, 8                      ; CSK_WIN, CSK_NWIN
    dw .items                       ; CSK_ITEMS
    dw 224, 38                      ; CSK_ADCX, CSK_ADCY: right, in the glass
    dw 30, 21                       ; CSK_ADRY, CSK_ADHH
    dw 60                           ; CSK_BARW
    dw .deco, 2                     ; CSK_DECO, CSK_NDECO
.win:                               ; x1, y1, x2, y2 at 320 wide, rows below
    dw  13,  6,  75, 18             ;   SPD 000
    dw  13, 24,  91, 36             ;   ALT 00000
    dw  13, 42,  75, 54             ;   HDG 040
    dw 109,  6, 171, 18             ;   THR 100
    dw 109, 24, 173, 31             ;   the throttle bar's slot
    dw  13, 58, 123, 70             ;   ON THE WATER
    dw   0, 75, 319, 87             ;   the message strip
    dw 109, 42, 171, 54             ;   UP 015 - the variometer
.items:
    dw  16,  9                      ;   SPD
    dw  16, 27                      ;   ALT
    dw  16, 45                      ;   HDG
    dw   0,  0                      ;   (the attitude indicator draws itself)
    dw 112,  9                      ;   THR
    dw  16, 61                      ;   the state
    dw 112, 25                      ;   the throttle bar
    dw   0, 78                      ;   the message
    dw 112, 45                      ;   THE VARIOMETER
.deco:                              ; kind, x, y, radius in rows, argument
    dw CSDK_SWITCH,  60, 68,  6, 1       ; the water rudder: DOWN...
    dw CSDK_SWITCH,  76, 68,  6, 0       ; ...and the gear, UP for a splash

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
    call cs_hscalex                 ; ...AND INTO BOX PIXELS, which the first
                                    ; build did not do: cs_pasp is rows per
                                    ; LOGICAL x unit (the 320-wide layout's),
                                    ; so the quotient is a logical radius and
                                    ; the ellipse wants box pixels. On CGA and
                                    ; Mode X the two are the same and it was
                                    ; round; on HERCULES the box is 640 wide
                                    ; and the bezel came out half as wide as
                                    ; it should be - the tall oval in every
                                    ; Hercules photograph of the panel
                                    ; (SPEC.md 88.9.2.1)
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
    call cs_adwin                   ; ...and the window, black
    ; --- and the instruments that only look the part (SPEC.md 88.9.3) -------
    mov si, [cs_plane]
    mov si, [si + CSP_COCKPIT]
    mov cx, [si + CSK_NDECO]
    jcxz .nodeco
    mov si, [si + CSK_DECO]
    mov al, CSI_PFG
    call cs_setink
    call cs_pclip
.d:
    push cx
    push si
    call cs_pdeco
    pop si
    pop cx
    add si, CSD_SIZE
    loop .d
    call cs_vclip
.nodeco:
    call cs_pclip                   ; ...and the four LABELS that never change
    call cs_plabels                 ; (88.9.4), under the panel's own clip and
    call cs_vclip                   ; OUTSIDE the decoration loop, which a
    ret                             ; cockpit with no decorations skips whole

; -----------------------------------------------------------------------------
; cs_pdeco - one decoration (SPEC.md 88.9.3). SI -> its five words; the ink
;            and the clip are the caller's. Clobbers everything
;
; Its radius is given in ROWS and the x radius derived through cs_pasp, the
; same way the attitude indicator's bezel is, so a dial is round on all three
; adapters rather than round on one and an egg on the others.
; -----------------------------------------------------------------------------
; -----------------------------------------------------------------------------
; cs_plabels - SPD, ALT, HDG and THR, once per target (SPEC.md 88.9.4)
;
; They were part of every reading: cs_pnum built 'ALT ' + five digits into one
; buffer and lettered the lot, so nine cells were drawn where five had
; changed - and on Mode X, where a cell is four bits deep and cs_panel was
; measured at 21.8% of the frame, that is most of the panel's cost. The
; label is drawn with the cockpit instead and the digits alone are redrawn.
; The variometer is NOT in this list: its label is UP or DN, which is the
; sign of the reading and changes with it.
; -----------------------------------------------------------------------------
cs_plabels:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    xor di, di                      ; DI = the item
.l:
    mov si, di
    shl si, 1
    mov si, [cs_plbl + si]
    or si, si
    jz .next                        ; this item has no fixed label
    mov bx, di
    push di
    push si
    call cs_pcell                   ; BX = its x, DX = its row
    pop si
    or bx, bx
    jz .n2                          ; ...and this cockpit has no such window
    call cs_pline
.n2:
    pop di
.next:
    inc di
    cmp di, CS_PI_THR
    jbe .l
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; the fixed label of items 0..CS_PI_THR; 0 where there is none
cs_plbl: dw cs_s_spd, cs_s_alt, cs_s_hdg, 0, cs_s_thr

cs_pdeco:
    mov [cs_dsi], si
    mov ax, [si + CSD_X]
    call cs_hscalex
    mov [cs_dcx], ax
    mov ax, [si + CSD_Y]
    add ax, [cs_pany]
    mov [cs_dcy], ax
    mov ax, [si + CSD_R]
    mov [cs_dry], ax
    mov ah, al                      ; rx = ry / aspect (AX = ry x 256)...
    xor al, al
    xor dx, dx
    div word [cs_pasp]
    call cs_hscalex                 ; ...and into box pixels (88.9.2.1)
    mov [cs_drx], ax
    mov ax, [si + CSD_ARG]
    mov [cs_darg], ax
    ; --- A DARK FACE FIRST, and it is not decoration on decoration: the
    ;     cockpit's face is a 25% dither (CSI_PFACE) and a white outline on
    ;     it reads as noise at this size. The instrument windows solve the
    ;     same problem the same way - a black ground, a white edge - so a
    ;     gauge gets the plate it would have in the metal ------------------
    mov al, CSI_PBG
    call cs_setink
    mov ax, [cs_dcx]
    sub ax, [cs_drx]
    mov bx, [cs_dcy]
    sub bx, [cs_dry]
    mov cx, [cs_dcx]
    add cx, [cs_drx]
    mov dx, [cs_dcy]
    add dx, [cs_dry]
    call cs_prect
    mov al, CSI_PFG
    call cs_setink
    mov si, [cs_dsi]
    cmp word [si + CSD_KIND], CSDK_SWITCH
    je .switch
    ; --- a dial: the bezel, then a needle from the centre at CSD_ARG -------
    mov ax, [cs_dcx]
    mov bx, [cs_dcy]
    mov cx, [cs_drx]
    mov dx, [cs_dry]
    call cs_ellipse
    mov ax, [cs_darg]               ; ...three quarters of the way out
    call cs_cos
    mov bx, [cs_drx]
    MUL14
    mov cx, ax
    sar cx, 1
    sar cx, 1
    sub ax, cx                      ; AX = 0.75 x rx cos
    add ax, [cs_dcx]
    mov [cs_dpx], ax
    mov ax, [cs_darg]
    call cs_sin
    mov bx, [cs_dry]
    MUL14
    mov cx, ax
    sar cx, 1
    sar cx, 1
    sub ax, cx                      ; AX = 0.75 x ry sin
    add ax, [cs_dcy]
    mov dx, ax
    mov cx, [cs_dpx]
    mov ax, [cs_dcx]
    mov bx, [cs_dcy]
    jmp cs_seg                      ; the needle
.switch:
    ; --- a toggle: a stalk up or down out of its plate --------------------
    mov ax, [cs_dcx]
    mov bx, [cs_dcy]
    mov cx, ax
    mov dx, [cs_dry]
    add dx, 1
    cmp word [cs_darg], 0
    je .down
    neg dx                          ; up
.down:
    add dx, bx
    jmp cs_seg

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
    mov cx, ax                      ; CX = cos
    mov ax, [cs_roll]
    call cs_sin
    pop bx                          ; BX = t
    imul bx                         ; DX:AX = t sin
    ; --- COS IS EXACTLY ZERO AT 90 DEGREES (SPEC.md 88.9.2.2) --------------
    ; The note here used to read "CX = cos, over 0.5 within MAXROLL", and
    ; that is true of a TRAINER. cs_att_free and cs_att_lag have no roll
    ; clamp at all (88.7.2), so an aerobatic aeroplane rolls straight through
    ; the vertical - and cs_sintab is 1024 entries over the turn, so cos
    ; reads 0 for the whole 64-unit window at +-90 and +-201 either side of
    ; it. A `idiv cx` there is a DIVIDE BY ZERO, and on an 8088 int 0 returns
    ; past it with AX undefined, which puts a garbage rise into a segment the
    ; walk then draws off the end of the shadow.
    mov bx, cx                      ; the guarded divide (85.5) answers +-30000
    call cs_cdiv                    ; rather than faulting, zero divisor and all
    mov bx, [cs_adhh]               ; ...and the rise is clamped to four times
    shl bx, 1                       ; the window's half height: past that the
    shl bx, 1                       ; bar is vertical however much further it
    cmp ax, bx                      ; would go, and every number stays in a
    jle .dyhi                       ; word
    mov ax, bx
.dyhi:
    neg bx
    cmp ax, bx
    jge .dylo
    mov ax, bx
.dylo:
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
