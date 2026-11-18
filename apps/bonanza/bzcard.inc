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
    cmp byte [bz_vga], 0        ; THE VGA's cell (SPEC.md 128.45.4): the part's
    je .cst                     ; store, a byte a plane at P y + S + c0 + cell
    BZ_VCALL BZV_CARD
    jmp short .nx
.cst:
    mov bx, dx
    shl bx, 1
    add bx, [bz_crdbs]
    and bx, 1fffh
    add bx, [bz_crdbk]
    mov [es:bx], ax
.nx:
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

; ---- the game's other cards (8c.4): built in bz_kbuf, then bz_card ---------------
; bz_kput - the NUL string at SI appended at DI (ours).  -> DI after it.
bz_kput:
    lodsb
    or al, al
    jz .e
    stosb
    jmp short bz_kput
.e:
    ret

; bz_knum - AX appended at DI in decimal (BX = 10: a ".d" before the last digit -
; tenths; BX = 0 none).  Clobbers AX, CX, DX.
bz_knum:
    ; STKBALANCE-LOOP: one digit pushed a turn (and a leading zero) and the second loop pops CX of them
    xor cx, cx
.d:
    xor dx, dx
    push bx
    mov bx, 10
    div bx
    pop bx
    push dx
    inc cx
    or ax, ax
    jnz .d
    cmp bx, 10                  ; tenths: at least "0.d"
    jne .o
    cmp cx, 2
    jae .o
    push ax                     ; (AX 0: a leading zero)
    inc cx
.o:
    pop ax
    add al, '0'
    cmp cx, 1
    jne .w
    cmp bx, 10
    jne .w
    mov byte [di], '.'
    inc di
.w:
    stosb
    loop .o
    ret

; bz_kinfo - THE INFO CARD (128.22.6): AL = the pad's course K.  Its NAME; its
; ball; LIMIT s; GOLD s and SILVER s; BEST s.t and the medal won, or NOT
; PLAYED; EXITS n OF m (the exits found of those the course has); and NOT
; SAVED while the last write of BONANZA.DAT was refused.  The slot is the one
; played (bz_dslot).  Drawn over the frozen frame (bz_card); bz_kinfow waits
; for a key and takes it away.  Preserves ES, nothing else.
bz_kinfo:
    mov [bz_ikc], al
    push es
    push ds
    pop es
    mov di, bz_kbuf
    mov al, [bz_ikc]            ; NAME
    mov ah, BZ_CRS_NAMEB
    mul ah
    add ax, bz_cnames
    xchg ax, si
    call bz_kput
    call bz_kend
    call bz_kk                  ; BALL <name> (seven bytes a ball)
    mov al, [bz_cballs + bx]
    mov ah, 7
    mul ah
    add ax, bz_ks_mats
    push ax
    mov si, bz_ks_ball
    call bz_kput
    pop si
    call bz_kput
    call bz_kend
    call bz_kk                  ; LIMIT s
    shl bx, 1
    push word [bz_clims + bx]   ; (bz_kput spends AL)
    mov si, bz_ks_limit
    call bz_kput
    pop ax
    xor bx, bx
    call bz_knum
    call bz_kend
    call bz_kk                  ; GOLD s  SILVER s (the medals' steps)
    shl bx, 1
    shl bx, 1
    push word [bz_cmedals + bx]
    mov si, bz_ks_gold
    call bz_kput
    pop ax
    call bz_ksec
    call bz_kk
    shl bx, 1
    shl bx, 1
    push word [bz_cmedals + bx + 2]
    mov si, bz_ks_silver
    call bz_kput
    pop ax
    call bz_ksec
    call bz_kend
    call bz_kk                  ; BEST s.t and its medal, or NOT PLAYED
    shl bx, 1
    call bz_dslot
    mov ax, [si + bx + BZD_SBEST]
    mov [bz_ibest], ax
    mov si, bz_ks_notp
    or ax, ax
    jz .np
    mov si, bz_ks_best
    call bz_kput
    mov ax, [bz_ibest]
    xor dx, dx                  ; tenths = steps x 2 / 11 (a step is 1/55 s)
    shl ax, 1
    rcl dx, 1
    mov cx, 11
    div cx
    mov bx, 10
    call bz_knum
    call bz_kk
    shl bx, 1
    shl bx, 1
    cmp word [bz_cmedals + bx], 0 ; (a course with no medals)
    je .nm
    mov ax, [bz_ibest]
    mov si, bz_ks_gold2
    cmp ax, [bz_cmedals + bx]
    jbe .med
    mov si, bz_ks_silver2
    cmp ax, [bz_cmedals + bx + 2]
    ja .nm
.med:
    call bz_kput
.nm:
    jmp short .bl
.np:
    call bz_kput
.bl:
    call bz_kend
    call bz_kk                  ; EXITS n OF m
    shl bx, 1
    call bz_dslot
    mov ax, [si + bx + BZD_SEXIT]
    xor cx, cx
.pc:
    or ax, ax
    jz .pd
    shr ax, 1
    adc cl, 0
    jmp short .pc
.pd:
    mov si, bz_ks_exits
    call bz_kput
    mov al, cl
    xor ah, ah
    xor bx, bx
    call bz_knum
    mov si, bz_ks_of
    call bz_kput
    call bz_kk
    mov al, [bz_cnex + bx]
    xor ah, ah
    xor bx, bx
    call bz_knum
    call bz_kend
    cmp byte [bz_dwf], 0        ; the last write refused (bz_dwrite's: the
    je .ns                      ; entry's in the bracket or the desktop's save)
    mov si, bz_ks_nosave
    call bz_kput
    call bz_kend
.ns:
    stosb                       ; (the list's end: AL is 0)
    pop es
    mov si, bz_kbuf
    jmp bz_card

; the card builder's three small steps: a line's NUL; BX = K; AX steps
; appended as whole seconds
bz_kend:
    xor al, al
    stosb
    ret
bz_kk:
    mov bl, [bz_ikc]
    xor bh, bh
    ret
bz_ksec:
    xor dx, dx
    mov cx, BZ_SECSTEPS
    div cx
    xor bx, bx
    jmp bz_knum

; bz_kinfow - the info card of course AL, WAITING (the frozen frame under it,
; the clock and the sound kept as bz_pause keeps them) for a key, which is
; taken; the next frame is written whole.  Clobbers AX, BX, CX, DX, SI, DI.
bz_kinfow:
    call bz_kinfo
.w:
    call bz_clk_sample
    call bzs_frame              ; (NOT once a retrace frame: a frame is 16.7-20 ms
    mov ah, 1                   ; against a sub-tick's 18.3, and one sample per
    int 16h                     ; frame misses reloads - the song ran at half
    jz .w                       ; tempo; the pause's own polling loop, 8R.12)
    call bz_drain
    mov ax, [bz_subs]           ; (a pause adds no steps: the sub-ticks the
    mov [bz_lsubs], ax          ; wait took are discarded, as bz_pause's)
    mov byte [bz_freq], 1
    ret

; bz_kwait - a card read: until a key is typed, or about four seconds of frames
bz_kwait:
    mov cx, 30                  ; half a second of keys DRAINED first: the
.d:                             ; arrows held from the play repeat
    call bz_drain
    mov al, FSXW_FRAME
    call OSAPI_FSX_WAIT
    loop .d
    mov cx, 210
.w:
    mov al, FSXW_FRAME
    call OSAPI_FSX_WAIT
    mov ah, 1
    int 16h
    jnz .k
    loop .w
    ret
.k:
    jmp bz_drain

; bz_kover - GAME OVER
bz_kover:
    mov si, bz_kover_l
    call bz_card
    jmp short bz_kwait

bz_ks_ball:  db 'BALL ', 0
bz_ks_mats:  db 'RUBBER', 0, 'STEEL', 0, 0, 'GLASS', 0, 0
bz_ks_limit: db 'LIMIT ', 0
bz_ks_gold:  db 'GOLD ', 0
bz_ks_silver: db '  SILVER ', 0
bz_ks_best:  db 'BEST ', 0
bz_ks_gold2: db '  GOLD', 0
bz_ks_silver2: db '  SILVER', 0
bz_ks_notp:  db 'NOT PLAYED', 0
bz_ks_exits: db 'EXITS ', 0
bz_ks_of:    db ' OF ', 0
bz_ks_nosave: db 'NOT SAVED', 0
bz_kover_l:  db 'GAME OVER', 0, 'ANY KEY', 0, 0
