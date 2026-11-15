; =============================================================================
; apps/bonanza/bzcard.inc - THE CARDS (wave 8c, SPEC.md 128.19.8): a box of
; text drawn INSIDE the bracket, over the frozen frame, and taken away by a
; full write of the next one ([bz_freq], the frame loop's).
;
; No drawing slot is legal after the mode set (SPEC.md 53.7), so the text is
; the desktop font's own 8 x 8 glyphs, copied out with OSAPI_FONT_GLYPHS
; before it (bz_fload, WireBall's wv_fontload), and written here straight
; into the page the CRTC shows: line y, cell c at
;     (y & (rl - 1)) * 2000h + ((2 S + (y >> lsh) rb + 2 c) & 1FFFh)
; S the CRTC start in words ([bz_S]), rl and rb the card's lines a row and
; bytes a row ([bz_rl], [bz_rb]).  A cell is a WORD on both cards: on the CGA
; eight 2-bit pixels, on the Hercules eight PAIRS of its 720 (360 x 200's
; pair pixels) - so one table doubles each bit of a nibble for both, a set
; bit colour 3 (lit), a clear one 0 (dark).
; =============================================================================

BZC_FIRST   equ 32              ; the glyphs copied: ' ' to '_' (the cards are
BZC_NGLYPH  equ 64              ; UPPER CASE)

; bz_fload - the glyphs 32 - 95 into bz_font (blank where the kernel's table
; has none).  Before the mode set (bz_fullscreen).  Preserves nothing.
bz_fload:
    push es
    call OSAPI_FONT_GLYPHS      ; DX:SI the table, AL the first code, AH the last
    mov [bz_ff], ax
    mov bp, si                  ; (the table's base: a register, never [bp])
    mov es, dx
    mov di, bz_font
    mov bl, BZC_FIRST
.ch:
    mov cx, 8
    cmp bl, [bz_ff]
    jb .blank
    cmp bl, [bz_ff + 1]
    ja .blank
    mov al, bl
    sub al, [bz_ff]
    xor ah, ah
    shl ax, 1
    shl ax, 1
    shl ax, 1
    add ax, bp
    mov si, ax
.cp:
    mov al, [es:si]
    mov [di], al
    inc si
    inc di
    loop .cp
    jmp short .nx
.blank:
    mov byte [di], 0
    inc di
    loop .blank
.nx:
    inc bl
    cmp bl, BZC_FIRST + BZC_NGLYPH
    jb .ch
    pop es
    ret

; bz_card - the list of NUL strings at SI (in our segment, a 0 byte after the
; last) in a box centred on the screen: a white rule round it, a cell of
; margin either side, 4 lines above and below.  Preserves ES.
bz_card:
    push es
    mov es, [bz_vseg]
    mov [bz_crdls], si
    xor cx, cx                  ; CX the lines, DX the widest
    xor dx, dx
.cnt:
    cmp byte [si], 0
    je .cdone
    inc cx
    xor bx, bx
.len:
    lodsb
    or al, al
    jz .lend
    inc bx
    jmp short .len
.lend:
    cmp bx, dx
    jbe .cnt
    mov dx, bx
    jmp short .cnt
.cdone:
    mov [bz_crdn], cx
    inc dx
    inc dx
    mov [bz_crdw], dx
    mov ax, [bz_W]
    sub ax, dx
    sar ax, 1
    mov [bz_crdc0], ax
    mov ax, cx
    shl ax, 1
    shl ax, 1
    shl ax, 1
    add ax, 8
    mov [bz_crdh], ax
    mov bx, BZ_LINES
    sub bx, ax
    shr bx, 1
    mov [bz_crdy0], bx
    xor bp, bp                  ; BP the box's line (a counter, never [bp])
.row:
    mov ax, [bz_crdy0]
    add ax, bp                  ; y
    mov bx, [bz_rl]
    dec bx
    and bx, ax
    mov cl, 13
    shl bx, cl
    mov [bz_crdbk], bx          ; (y & (rl - 1)) * 2000h
    mov cl, [bz_lsh]
    shr ax, cl
    mul word [bz_rb]            ; (y >> lsh) rb
    mov bx, [bz_S]
    shl bx, 1
    add ax, bx
    mov bx, [bz_crdc0]
    shl bx, 1
    add ax, bx
    mov [bz_crdbs], ax          ; ...+ 2 S + 2 c0
    xor di, di                  ; DI the line's string, 0 none
    mov ax, bp
    sub ax, 4
    js .noline
    mov bx, ax
    and bx, 7
    mov [bz_crdgr], bx            ; the glyph's row
    mov cl, 3
    shr ax, cl
    cmp ax, [bz_crdn]
    jae .noline
    mov cx, ax
    mov si, [bz_crdls]
.walk:
    jcxz .got
.sk:
    lodsb
    or al, al
    jnz .sk
    loop .walk
.got:
    mov di, si
.noline:
    xor dx, dx                  ; DX the cell
.cell:
    or bp, bp                   ; the rules, top and bottom
    jz .rule
    mov bx, [bz_crdh]
    dec bx
    cmp bp, bx
    je .rule
    xor ax, ax
    or dx, dx                   ; (cell 0 is the margin)
    jz .edge
    or di, di
    jz .edge
    mov al, [di]
    or al, al
    jz .z                       ; (the string's end: DI stays on its NUL)
    inc di
    sub al, BZC_FIRST
    jb .z
    cmp al, BZC_NGLYPH
    jae .z
    xor ah, ah
    shl ax, 1
    shl ax, 1
    shl ax, 1
    add ax, [bz_crdgr]
    mov bx, ax
    mov al, [bz_font + bx]      ; the glyph row's 8 bits ...
    mov bl, al
    and bx, 15
    mov ah, [bz_x4 + bx]        ; ...the right four doubled into the 2nd byte
    mov bl, al
    shr bl, 1
    shr bl, 1
    shr bl, 1
    shr bl, 1
    mov al, [bz_x4 + bx]        ; ...the left four into the 1st
    jmp short .edge
.z:
    xor ax, ax
.edge:
    or dx, dx                   ; the rules, left and right
    jnz .re
    or al, 0c0h
.re:
    mov bx, [bz_crdw]
    dec bx
    cmp dx, bx
    jne .st
    or ah, 03h
    jmp short .st
.rule:
    mov ax, 0ffffh
.st:
    mov bx, dx
    shl bx, 1
    add bx, [bz_crdbs]
    and bx, 1fffh
    add bx, [bz_crdbk]
    mov [es:bx], ax
    inc dx
    cmp dx, [bz_crdw]
    jb .cell
    inc bp
    cmp bp, [bz_crdh]
    jb .row
    pop es
    ret

; a nibble's four bits each doubled: the CGA's colour 3 on 0, the Hercules's
; lit pair on a dark one
bz_x4:      db 00h, 03h, 0ch, 0fh, 30h, 33h, 3ch, 3fh
            db 0c0h, 0c3h, 0cch, 0cfh, 0f0h, 0f3h, 0fch, 0ffh

; THE PAUSE CARD (8c.4): the game's (R a retry, a life; Esc the map, a life)
; and a free play's
bz_pcardg:  db 'PAUSED', 0, 'P RESUME  R RETRY  ESC MAP', 0, 0
bz_pcardf:  db 'PAUSED', 0, 'P RESUME  ESC QUIT', 0, 0   ; (and the pathway's)
