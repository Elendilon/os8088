; =============================================================================
; apps/tithe/titxt.inc - TITHE's OWN TEXT, drawn into a band (SPEC.md 97.4.1)
;
; WHY THE PACKAGE DRAWS ITS OWN. A character has six stats and four of them
; have to be on the board; at the system 8x8 a CGA cell's stat column holds
; TWO of the four and a CGA card row holds a name OR the numbers. The face
; that answers it is 6x6, and `OSAPI_FONT_RUN` draws the system face and no
; other - so the choice was a smaller face or fewer numbers.
;
; IT IS ALSO FASTER, WHICH WAS NOT THE REASON. A card was a fill, a second
; fill, a frame, two runs, three icon blits and the unit - a dozen arrivals at
; ~800 us each (SPEC.md 97.5's own calibration). Composed, it is one
; `OSAPI_GFX_BLIT1`. The saving is real but it is not why this exists: nothing
; here is on the animation clock, because a card is drawn when the hover
; changes and a cell's numbers at most once a round (TITHE-PLAN 8).
;
; A GLYPH IS ONE BYTE A ROW, MSB FIRST, and the cell width IS the advance - so
; a run needs no gap put between its glyphs and the composer needs no kerning.
; tools/os88titheface.py emits tifaces.inc and asserts both.
; =============================================================================

; -----------------------------------------------------------------------------
; ti_face_set - select face AX (0..TI_FACES-1) and cache its shape
; Preserves every register.
; -----------------------------------------------------------------------------
ti_face_set:
    push ax
    push bx
    mov [ti_face], ax
    mov bx, ax
    shl bx, 1
    mov bx, [bx + ti_face_tab]
    mov [ti_fdata], bx
    mov bx, ax
    mov al, [bx + ti_face_w]
    xor ah, ah
    mov [ti_fw], ax
    mov al, [bx + ti_face_h]
    xor ah, ah
    mov [ti_fh], ax
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; ti_chidx - AL = a byte -> AL = its glyph, 0FFh for one the face has not got
; Preserves every register bar AX and the flags.
;
; THE FACES ARE 48 CONSECUTIVE GLYPHS AND NOT ASCII (tifaces.inc): the package
; draws capitals, digits, a space, four marks and the seven icons and nothing
; else, so a 91-entry table would be 43 glyphs nobody ever asks for. Codes 1..7
; arrive as themselves - an icon is a glyph like any other, which is what lets
; one run carry `heart 12` with no second call and no second alignment.
; -----------------------------------------------------------------------------
ti_chidx:
    cmp al, 7
    ja .notic
    or al, al
    jz .bad
    dec al                          ; 1..7 -> 0..6
    ret
.notic:
    cmp al, ' '
    jne .dig
    mov al, 7
    ret
.dig:
    cmp al, '0'                     ; ...AND A MARK BELOW '0' IS STILL A MARK.
    jb .marks                       ; This said `jb .bad`, so every one of
                                    ; `+ , - . /` answered "no such glyph" and
                                    ; drew a hole - and the defect was invisible
                                    ; because the only mark anything wrote was
                                    ; the COLON, which sorts above '9' and
                                    ; reaches .marks the long way round.
    cmp al, '9'
    ja .upper
    sub al, '0' - 8
    ret
.upper:
    cmp al, 'a'                     ; a lower-case byte is drawn as its capital
    jb .cap                         ; rather than refused: the card names are
    cmp al, 'z'                     ; data and a stray case is not worth a
    ja .cap                         ; blank in the middle of a word
    sub al, 32
.cap:
    cmp al, 'A'
    jb .marks
    cmp al, 'Z'
    ja .marks
    sub al, 'A' - 18
    ret
.marks:
    mov ah, 44                      ; the marks, in tifaces.inc's own order
    cmp al, '-'
    je .mk
    inc ah
    cmp al, '.'
    je .mk
    inc ah
    cmp al, '+'
    je .mk
    inc ah
    cmp al, '/'
    je .mk
    inc ah
    cmp al, ','                     ; A COMMA AND A COLON ARE PROSE, and the
    je .mk                          ; HUD carries prose now (SPEC.md 97.4.8).
    inc ah                          ; They were not in the set, ti_chidx
    cmp al, ':'                     ; answered 0FFh and ti_glyph then drew
    je .mk                          ; NOTHING - no box, no fallback, a hole the
.bad:                               ; width of a cell that nothing reports
    mov al, 0FFh
    ret
.mk:
    mov al, ah
    xor ah, ah
    ret
; -----------------------------------------------------------------------------
; ti_glyph - OR glyph AL into the band at (BX = x) on the row DI points at
; in:  ES:DI = the BAND ROW's own base, BP = its stride, [ti_fw]/[ti_fh]/[ti_fdata]
; Preserves BX, DI, BP and ES; clobbers AX, CX, DX, SI.
;
; THE ROW IS THE CALLER'S. It used to take a y in DX and resolve the row here,
; which is one 16-bit multiply a GLYPH - and a card is ~55 of them, so the run
; paid for the same row fifty-five times over. `ti_text` does it once. What is
; left per glyph is the byte within the row, the pen's bit, and the multiply
; that finds the glyph itself.
;
; IT PRESERVES LESS THAN IT USED TO, and deliberately: a push and its pop are
; ~27 cycles of an 8088 and six pairs of them were a fifth of a glyph.
;
; THE X NEED NOT BE A MULTIPLE OF EIGHT. A glyph is at most 8 bits, so it lands
; in at most two destination bytes: the row goes into AH, the pair is shifted
; right by x&7, and the two halves are ORed. That is the whole of why a card
; can be composed at any pitch the layout hands it, where `gfx_blit1` would
; refuse the band itself at an unaligned x (SPEC.md 5.4.2).
; -----------------------------------------------------------------------------
ti_glyph:
    cmp al, 0FFh
    je .out
    push di
    push bx
    mov cx, bx
    and cx, 7                       ; CL = the pen's bit inside its byte
    shr bx, 1
    shr bx, 1
    shr bx, 1
    add di, bx                      ; ...and the byte within the row
    xor ah, ah
    mul word [ti_fh]                ; AX = glyph * rows
    mov si, [ti_fdata]
    add si, ax                      ; SI -> its first row
    mov dx, [ti_fh]
.row:
    or dx, dx
    jz .done
    mov ah, [si]                    ; the glyph's row, MSB first...
    xor al, al
    shr ax, cl                      ; ...placed at the pen's own bit
    or [es:di], ah
    or [es:di + 1], al              ; the band is padded, so byte+1 is ours
    inc si
    add di, bp
    dec dx
    jmp short .row
.done:
    pop bx
    pop di
.out:
    ret

; -----------------------------------------------------------------------------
; ti_text - OR the NUL-terminated run at DS:SI into the band
; in:  ES:DI = the band's base, BP = stride, BX = x, DX = y
; out: BX = the x after the last glyph. Preserves every other register.
;
; IT RESOLVES THE ROW ONCE and hands it to every glyph (see ti_glyph).
; -----------------------------------------------------------------------------
ti_text:
    push ax
    push cx
    push dx
    push si
    push di
    mov ax, dx
    mul bp                          ; ...ONE multiply for the whole run
    add di, ax
.ch:
    lodsb
    or al, al
    jz .out
    call ti_chidx
    push si
    call ti_glyph
    pop si
    add bx, [ti_fw]
    jmp short .ch
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop ax
    ret


; -----------------------------------------------------------------------------
; ti_textw - AX = what ti_text would advance BX by, for DS:SI
; Preserves every register bar AX.
; -----------------------------------------------------------------------------
ti_textw:
    push bx
    push si
    xor bx, bx
.ch:
    lodsb
    or al, al
    jz .out
    add bx, [ti_fw]
    jmp short .ch
.out:
    mov ax, bx
    pop si
    pop bx
    ret
