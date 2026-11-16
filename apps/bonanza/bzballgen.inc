; bzballgen.inc - the ball parts GENERATED AT FETCH (SPEC.md 128.25.5, wave 9
; story 9.4).
;
; The ball part on the disk is BZB3: BZB2's header, then ZEROS, and a small
; BLOCK at the head of the squash slot (BZ_BG_BLK) - the material's 2-bit
; template, its phase table, its ellipse rows - and, for glass, its shatter
; entries as they are.  bz_ballgen turns that into BZB2 EXACTLY, byte for byte,
; IN PLACE, forwards: the masks, the 64 roll frames (the template and a
; separable sum, A[x][fx] + A[y][fy] < T), the squash entries, the shadow
; masks and rubber's stretch.  Every write is behind every read it needs (the
; block is read to scratch first; the phase table, which the frames read in
; place, is dead before the squash entries overwrite it), and the tool proves it by
; running THIS routine under an emulated 8086 on the stored file
; (tools/bzballchk.py, `make bonanza-check`).
;
; The planes: a 16 px row is a WORD per bit plane, pixel x in bit 15 - x.  A
; frame row is the template's low and high planes with the INK bits (the sum
; test, tex pixels only) ORed in; bg_ilv interleaves the two planes into the
; 2-bit fields (32 bits) and bg_p5 shifts that right by 2 s bits into the five
; bytes, the fill being 0 for a frame and 11 for a mask (kept).  A squash or
; stretch entry is a shape (rows of n, the ellipse's half width) whose ring is
; BLACK (a pixel with a 4-neighbour outside), pressed from the round frame 0
; (rows: Q planes; columns, the stretch: bg_gatq) and, glass, a see-through
; checker inside the ring.
;
; DS = ours (the scratch is bz_boxbuf, 1024 bytes that nothing uses until the
; bracket), AX = the part's segment (ES, a selector on kern_mega: the part is
; read and written through it at offsets inside its length, nothing through
; CS).  Preserves AX and ES only.
; -----------------------------------------------------------------------------
BG_SC       equ bz_boxbuf
BG_RQLO     equ BZ_BG_PRE                   ; offsets from bz_boxbuf: frame 0's planes,
BG_RQHI     equ BG_RQLO + 32                ; clear = the base colour
BG_ROP      equ BG_RQHI + 32                ; an entry's opaque, low and high planes
BG_RLO      equ BG_ROP + 32
BG_RHI      equ BG_RLO + 32
BG_RSS      equ BG_RHI + 34                 ; the shape rows (one guard word either side)
BG_RS2      equ BG_RSS + 34                 ; byte: the shift, 2 s
BG_RP       equ BG_RS2 + 1                  ; byte: the shadow's parity copy
BG_RH       equ BG_RP + 1                   ; byte: the squash's height (16: none)
BG_RCHK     equ BG_RH + 1                   ; word: the checker's row pattern
BG_RBH      equ BG_RCHK + 2                 ; word: FFFFh for rubber (its base colour is magenta)
BG_RGX      equ BG_RBH + 2                  ; word: the frame's x row of the phase table
BG_RGY      equ BG_RGX + 2                  ; word: ...and its y row
BG_RTAB     equ BG_RGY + 2                  ; H[256]: a byte's bits spread to the odd bits
BG_REND     equ BG_RTAB + 512
%if BG_REND > 4 * BZ_BOXB
 %error "bz_ballgen: the scratch does not fit bz_boxbuf"
%endif
BG_TAB      equ bz_boxbuf + BG_RTAB
BG_QLO      equ bz_boxbuf + BG_RQLO
BG_QHI      equ bz_boxbuf + BG_RQHI
BG_OP       equ bz_boxbuf + BG_ROP
BG_LO       equ bz_boxbuf + BG_RLO
BG_HI       equ bz_boxbuf + BG_RHI
BG_SS       equ bz_boxbuf + BG_RSS
BG_S2       equ bz_boxbuf + BG_RS2
BG_P        equ bz_boxbuf + BG_RP
BG_H        equ bz_boxbuf + BG_RH
BG_CHK      equ bz_boxbuf + BG_RCHK
BG_BH       equ bz_boxbuf + BG_RBH
BG_GX       equ bz_boxbuf + BG_RGX
BG_GY       equ bz_boxbuf + BG_RGY

bz_ballgen:
    push ax
    push es                     ; (ES back as op_fetch left it: the ball's
    cld                         ; selector must not outlive the loop in ES)
    mov es, ax
    mov si, BZ_BG_BLK           ; the block's prefix to scratch (the phase
    mov di, BG_SC               ; table stays where it is, read through ES)
    mov cx, BZ_BG_PRE
.cp:
    es lodsb
    mov [di], al
    inc di
    loop .cp
    mov bx, BG_TAB              ; H[b], the spread table
    xor dx, dx
.tb:
    mov al, dl
    mov cx, 8
    xor si, si
.tbl:
    shl al, 1
    rcl si, 1
    shl si, 1
    loop .tbl
    mov [bx], si
    inc bx
    inc bx
    inc dl
    jnz .tb
    xor ax, ax                  ; the shape rows' guards
    mov [BG_SS - 2], ax
    mov [BG_SS + 32], ax
    cmp byte [es:10], al        ; rubber: its base colour is magenta (10), the
    jne .nr                     ; others' cyan (01)
    dec ax
.nr:
    mov [BG_BH], ax
    ; --- the masks: the silhouette at the four shifts
    mov di, BZ_BAL_MASKOFF
    mov byte [BG_S2], 0
.ms:
    xor bp, bp
.mr:
    mov bx, [ds:bp + BG_SC + BZ_BG_O]
    not bx
    call bg_em_m
    inc bp
    inc bp
    cmp bp, 32
    jb .mr
    add byte [BG_S2], 2
    cmp byte [BG_S2], 8
    jb .ms
    ; --- the 64 roll frames
    mov byte [BG_S2], 0
    mov word [BG_GY], BZ_BG_G
.fy:
    mov word [BG_GX], BZ_BG_G
.fx:
    xor bp, bp
.fr:
    mov bx, [ds:bp + BG_SC + BZ_BG_CLO]
    xor bx, [ds:bp + BG_SC + BZ_BG_CHI]
    jz .ni                      ; no tex pixel in this row: no ink
    mov bx, [BG_GY]
    add bx, bp
    mov dx, [BG_SC + BZ_BG_T]
    sub dx, [es:bx]             ; T - the y term
    mov si, [BG_GX]
    mov cx, 16
.ink:
    es lodsw                    ; the x term
    cmp ax, dx
    rcl bx, 1                   ; CF = ink: the x term is under T - y term
    loop .ink
    mov si, [ds:bp + BG_SC + BZ_BG_CLO]
    xor si, [ds:bp + BG_SC + BZ_BG_CHI]
    and bx, si                  ; the tex pixels: low xor high
.ni:
    mov ax, [ds:bp + BG_SC + BZ_BG_CLO]
    mov dx, [ds:bp + BG_SC + BZ_BG_CHI]
    or ax, bx                   ; AX = the low plane
    or dx, bx                   ; DX = the high plane
    cmp di, BZ_BAL_FRMOFF + BZ_BAL_FRMB
    jae .nq
    mov bx, [ds:bp + BG_SC + BZ_BG_O]   ; frame 0: Q = the frame, with the
    not bx                              ; base colour where it is clear
    mov si, [BG_BH]
    not si
    and si, bx
    or si, ax
    mov [ds:bp + BG_QLO], si
    and bx, [BG_BH]
    or bx, dx
    mov [ds:bp + BG_QHI], bx
.nq:
    mov bx, dx
    mov si, ax
    call bg_em_f
    inc bp
    inc bp
    cmp bp, 32
    jb .fr
    add byte [BG_S2], 2
    and byte [BG_S2], 6
    add word [BG_GX], 32
    cmp word [BG_GX], BZ_BG_G + 256
    jb .fx
    add word [BG_GY], 32
    cmp word [BG_GY], BZ_BG_G + 256
    jb .fy
    ; --- the squash, the shadow, rubber's stretch (the shatter, glass's, is stored)
    mov bx, BG_SC + BZ_BG_SQ0
    call bg_ent
    mov bx, BG_SC + BZ_BG_SQ1
    call bg_ent
    call bg_shd
    cmp byte [es:BZB_NSTR], 0
    je .out
    call bg_gatq
    mov bx, BG_SC + BZ_BG_STR
    call bg_ent
.out:
    pop es
    pop ax
    ret

; bg_em_m - a MASK row: BX = the KEEP plane; bg_em_f - a FRAME row: BX = the
; high plane, SI = the low; both at shift [BG_S2], to ES:DI (DI + 5)
bg_em_m:
    mov si, bx
    call bg_ilv
    xor bh, bh                  ; the fill is 11
    jmp short bg_emx
bg_em_f:
    call bg_ilv
    mov bh, 1                   ; the fill is 00
bg_emx:
    mov cl, [BG_S2]
; bg_p5 - DX:AX the 16 px as 32 bits, CL = 2 s, BH 0 (fill 11) or 1 (fill 00):
; the 40 bits shifted right by CL and stored
bg_p5:
    mov bl, bh
    dec bl                      ; the right fill: FFh or 0
    or cl, cl
    jz .st
.sh:
    cmp bh, 1                   ; CF = the fill bit
    rcr dx, 1
    rcr ax, 1
    rcr bl, 1
    dec cl
    jnz .sh
.st:
    xchg ax, dx
    xchg al, ah
    stosb
    mov al, ah
    stosb
    mov al, dh
    stosb
    mov al, dl
    stosb
    mov al, bl
    stosb
    ret

; bg_ilv - BX the high plane, SI the low -> DX:AX, pixel x's field in bits
; 31 - 2 x .. 30 - 2 x (the 32 shifts leave nothing of what AX and DX held)
bg_ilv:
    mov cx, si
    mov al, bh
    call .lk
    mov dx, ax                  ; H[hi plane's high byte]
    mov al, ch
    call .lk
    shr ax, 1
    or dx, ax
    mov al, bl
    call .lk
    mov bx, ax
    mov al, cl
    call .lk
    shr ax, 1
    or ax, bx
    ret
.lk:
    xor ah, ah                  ; AX = H[AL]: the byte's bits spread to the odd
    mov si, ax                  ; bits of a word
    shl si, 1
    mov ax, [si + BG_TAB]
    ret

; bg_shape - BX = a shape table (height, then 16 rows of n): the rows' words
; into BG_SS, row y = bits 8 - n .. 7 + n of 16 (0 for n = 0)
bg_shape:
    mov al, [bx]
    mov [BG_H], al
    lea si, [bx + 1]
    mov bx, BG_SS
    mov dl, 16
.s:
    lodsb
    mov dh, al
    mov cl, al
    add cl, cl
    mov ax, 1
    shl ax, cl
    dec ax
    mov cl, 8
    sub cl, dh
    shl ax, cl
    mov [bx], ax
    inc bx
    inc bx
    dec dl
    jnz .s
    ret

; bg_ent - an entry (squash 0 or 1, the stretch): BX = its shape table; ES:DI
; gets its four shifts of two identical copies, each (16 mask rows, 16 frame
; rows).  Row y of the shape: I = the interior (all four neighbours in), the
; ring = S and not I is BLACK, glass's checker K = I and (x + y even) is
; see-through, so opaque = S xor K and coloured = I xor K; the colour of a
; coloured pixel is the Q pixel at row sy = 15 - ((15 - y) 16) / h (h 16, the
; stretch: y itself - its columns were pressed by bg_gatq).
bg_ent:
    call bg_shape
    xor ax, ax
    cmp byte [es:10], 2
    jne .nc
    mov ax, 0AAAAh
.nc:
    mov [BG_CHK], ax
    xor bp, bp
.y:
    mov ax, [ds:bp + BG_SS]
    mov dx, ax
    shl dx, 1
    and dx, ax
    mov cx, ax
    shr cx, 1
    and dx, cx
    and dx, [ds:bp + BG_SS - 2]
    and dx, [ds:bp + BG_SS + 2] ; DX = I
    mov cx, [BG_CHK]
    ror word [BG_CHK], 1
    and cx, dx                  ; CX = K
    xor ax, cx
    mov [ds:bp + BG_OP], ax
    xor dx, cx                  ; DX = the coloured pixels
    mov ax, bp
    shr ax, 1                   ; y
    neg al
    add al, 15
    mov cl, 4
    shl ax, cl                  ; (15 - y) 16
    mov bl, [BG_H]
    div bl
    neg al
    add al, 15                  ; sy
    xor ah, ah
    shl ax, 1
    mov si, ax
    mov ax, [si + BG_QLO]
    and ax, dx
    mov [ds:bp + BG_LO], ax
    mov ax, [si + BG_QHI]
    and ax, dx
    mov [ds:bp + BG_HI], ax
    inc bp
    inc bp
    cmp bp, 32
    jb .y
    mov byte [BG_S2], 0
.sh:
    xor bp, bp
.m:
    mov bx, [ds:bp + BG_OP]
    not bx
    call bg_em_m
    inc bp
    inc bp
    cmp bp, 32
    jb .m
    xor bp, bp
.f:
    mov bx, [ds:bp + BG_HI]
    mov si, [ds:bp + BG_LO]
    call bg_em_f
    inc bp
    inc bp
    cmp bp, 32
    jb .f
    push ds                     ; the second copy: the first, again
    push es
    pop ds
    mov si, di
    sub si, 2 * BZ_BAL_FRMB * 2 / 2
    mov cx, BZ_BAL_FRMB
    rep movsw
    pop ds
    add byte [BG_S2], 2
    cmp byte [BG_S2], 8
    jb .sh
    ret

; bg_shd - the shadow masks: parity p, shift s, row r (6): the ellipse's row
; with the world checker (x + s + p + r even) cleared, AND only
bg_shd:
    mov bx, BG_SC + BZ_BG_SHD
    call bg_shape
    mov byte [BG_P], 0
.p:
    mov byte [BG_S2], 0
.s:
    mov cl, [BG_S2]
    shr cl, 1
    add cl, [BG_P]
    mov ax, 0AAAAh
    ror ax, cl
    mov [BG_CHK], ax
    xor bp, bp
.r:
    mov bx, [ds:bp + BG_SS]
    and bx, [BG_CHK]
    ror word [BG_CHK], 1
    not bx
    call bg_em_m
    inc bp
    inc bp
    cmp bp, 12
    jb .r
    add byte [BG_S2], 2
    cmp byte [BG_S2], 8
    jb .s
    inc byte [BG_P]
    cmp byte [BG_P], 2
    jb .p
    ret

; bg_gatq - rubber's stretch presses the round frame's COLUMNS: every Q row
; (32 words) is rebuilt with pixel x = the old pixel SX[x] - 1... (SX holds
; sx + 1: the shift whose last bit out is pixel sx)
bg_gatq:
    mov bp, BG_QLO
.w:
    mov bx, [ds:bp]
    mov si, BG_SC + BZ_BG_SX
    mov ch, 16
.g:
    mov cl, [si]
    inc si
    mov ax, bx
    rol ax, cl                  ; CF = old bit 16 - CL, SHL's carry, but DEFINED
    rcl dx, 1                   ; at CL = 16 on a 286+ too (SHL's is not: kern_mega)
    dec ch
    jnz .g
    mov [ds:bp], dx
    inc bp
    inc bp
    cmp bp, BG_QLO + 64
    jb .w
    ret
