; bzballgen.inc - the ball parts GENERATED AT FETCH (SPEC.md 128.25.5, wave 9
; story 9.4).
;
; The ball part on the disk is BZB3: BZB2's header, then ZEROS, and a small
; BLOCK at the head of the squash slot (BZ_BG_BLK) - the material's 2-bit
; template, its RANK-CODED phase table, its ellipse rows - and, for glass, its
; shatter entries as they are.  bz_ballgen turns that into BZB2 EXACTLY, byte
; for byte, IN PLACE, forwards: the masks, the 64 roll frames, the squash
; entries, the shadow masks and rubber's stretch.  Every write is behind every
; read it needs (the block's prefix is read to scratch first; the rank tables,
; which the frames read in place, are dead before the squash entries overwrite
; them), and the tool proves it by running THIS routine under an emulated 8086
; on the stored file (tools/bzballchk.py, `make bonanza-check`).
;
; THE SPEED (128.25.5.1): a row is 2 bits a pixel, five bytes at its shift.
; A roll frame's row is BASE | (P & TEX): BASE the template's colours, TEX its
; texture pixels (both spread to 2 bits at the frame's shift, built once a
; shift), P the INK, one entry of a per-phase MASK TABLE: ink at column x of
; phase fx, row j is XR[fx][x] <= YE[j] (the tool's rank coding of the
; separable sum), so P[k] is the columns whose XR <= k, spread to 2 bits at the
; shift - built once a phase, eight times a ball.  A row whose YE is 0 has no
; ink in any phase and is BASE alone.  Every other row (masks, squash, shadow,
; stretch) is a byte-table spread (bg_sp, bg_il) and a 2-bit shift of the five
; bytes in registers (BG_SH2) for each next shift.
;
; DS = ours (the scratch is bz_boxbuf, 1024 bytes that nothing uses until the
; bracket; the constant bg_nib is read through DS, the package's image), AX =
; the part's segment (ES, a selector on kern_mega: the part is read and
; written through it at offsets inside its length, nothing through CS).
; Preserves AX and ES only.
; -----------------------------------------------------------------------------
BGR_TB      equ BZ_BG_PRE + 512             ; (offsets in bz_boxbuf, for the checks)
BGR_V       equ BGR_TB + 160 + BZ_BG_PMAX * BZ_BG_PSTR
BG_SC       equ bz_boxbuf                   ; the block's prefix (BZ_BG_PRE bytes)
BG_HH       equ BG_SC + BZ_BG_PRE           ; 256: a byte's HIGH nibble spread to bits 7, 5, 3, 1
BG_HL       equ BG_HH + 256                 ; 256: ...its LOW nibble
BG_TB       equ bz_boxbuf + BGR_TB          ; frames: 16 rows x (BASE 5, TEX 5) at the shift
BG_P        equ BG_TB + 160                 ; frames: the mask table, BZ_BG_PMAX x BZ_BG_PSTR
BG_V        equ bz_boxbuf + BGR_V
BG_SEG      equ BG_V                        ; word: the part's segment
BG_I        equ BG_V + 2                    ; word: a row's offset, 2 r
BG_TBP      equ BG_V + 4                    ; word: the TB row
BG_BH       equ BG_V + 6                    ; word: FFFFh for rubber (its base colour is magenta)
BG_CHK      equ BG_V + 8                    ; word: the checker's row pattern
BG_COL      equ BG_V + 10                   ; word: an entry row's coloured pixels
BG_EDI      equ BG_V + 12                   ; word: an entry row's mask row at shift 0
BG_S        equ BG_V + 14                   ; byte: the shift
BG_FX       equ BG_V + 15                   ; byte: the phase fx
BG_H        equ BG_V + 16                   ; byte: an entry's height (16: none)
BG_PAR      equ BG_V + 17                   ; byte: the shadow's parity
BG_END      equ BG_V + 18
; ...and over TB and P once the frames are done:
BG_QLO      equ BG_TB                       ; frame 0's planes, clear = the base colour
BG_QHI      equ BG_TB + 32
BG_SS       equ BG_TB + 66                  ; the shape rows (one guard word either side)
%if BGR_V + 18 > 4 * BZ_BOXB
 %error "bz_ballgen: the scratch does not fit bz_boxbuf"
%endif

; BG_SH2 - AL, AH, DL, DH, CL (bytes 0..4 of a row, in memory order) one pixel
; right; the pixel in is CH (C0h: 11, a mask's; 0: 00, a frame's)
%macro BG_SH2 0
    shr al, 1
    rcr ah, 1
    rcr dl, 1
    rcr dh, 1
    rcr cl, 1
    shr al, 1
    rcr ah, 1
    rcr dl, 1
    rcr dh, 1
    rcr cl, 1
    or al, ch
%endmacro

bz_ballgen:
    push ax
    push es
    cld
    mov [BG_SEG], ax
    push ds                     ; the block's prefix to scratch (the rank
    pop es                      ; tables stay where they are, read through ES)
    push ds
    mov ds, ax
    mov si, BZ_BG_BLK
    mov di, BG_SC
    mov cx, BZ_BG_PRE / 2
    rep movsw
    pop ds
    mov dx, 16                  ; HH[b] = N[b >> 4]: sixteen runs of N[h]
    mov si, bg_nib
.hh:
    lodsb
    mov cx, 16
    rep stosb
    dec dx
    jnz .hh
    mov dl, 16                  ; HL[b] = N[b & 15]: sixteen copies of N
.hl:
    mov si, bg_nib
    mov cx, 8
    rep movsw
    dec dx
    jnz .hl
    mov es, [BG_SEG]
    xor bx, bx                  ; BH = 0: BX indexes the byte tables by BL
    mov ax, bx
    cmp byte [es:10], al        ; rubber: its base colour is magenta (10), the
    jne .nr                     ; others' cyan (01)
    dec ax
.nr:
    mov [BG_BH], ax
    ; --- shift 0: the masks at their four shifts, and TB
    mov word [BG_TBP], BG_TB
    mov [BG_I], bx
    mov di, BZ_BAL_MASKOFF
    mov bp, BZ_BAL_MASKSH
.tb:
    mov si, [BG_I]
    mov dx, [si + BG_SC + BZ_BG_O]
    not dx
    call bg_sp
    mov cx, 0C0FFh              ; the fill: 11
    call bg_put4
    sub di, 3 * BZ_BAL_MASKSH - BZ_BAL_RB
    mov si, [BG_I]
    mov dx, [si + BG_SC + BZ_BG_CLO]
    xor dx, [si + BG_SC + BZ_BG_CHI]
    call bg_sp                  ; TEX
    mov si, [BG_TBP]
    mov [si + 5], ax
    mov [si + 7], dx
    mov [si + 9], bh
    mov si, [BG_I]
    mov dx, [si + BG_SC + BZ_BG_CHI]
    mov cx, [si + BG_SC + BZ_BG_CLO]
    call bg_il                  ; BASE
    mov si, [BG_TBP]
    mov [si], ax
    mov [si + 2], dx
    mov [si + 4], bh
    add word [BG_TBP], 10
    add word [BG_I], 2
    cmp word [BG_I], 32
    jb .tb
    ; --- the 64 roll frames, by shift: phases s and s + 4, eight frames each
    mov [BG_S], bh
.s:
    mov al, [BG_S]
    mov [BG_FX], al
.fx:
    call bg_pb
    mov al, [BG_FX]
    mov ah, BZ_BAL_FRMB
    mul ah
    add ax, BZ_BAL_FRMOFF
    mov di, ax                  ; frame fx, then + 8 a fy
    mov bp, BZ_BG_YE
.fy:
    mov si, BG_TB
    mov cx, BZ_BAL_ROWS
.row:
    mov bl, [es:bp]
    inc bp
    or bl, bl
    jz .base
    mov ax, [bx + BG_P]
    and ax, [si + 5]
    or ax, [si]
    stosw
    mov ax, [bx + BG_P + 2]
    and ax, [si + 7]
    or ax, [si + 2]
    stosw
    mov al, [bx + BG_P + 4]
    and al, [si + 9]
    or al, [si + 4]
    stosb
    add si, 10
    loop .row
    jmp short .fe
.base:
    movsw                       ; no ink in any phase: BASE alone
    movsw
    movsb
    add si, 5
    loop .row
.fe:
    add di, 7 * BZ_BAL_FRMB
    cmp bp, BZ_BG_YE + 128
    jb .fy
    add byte [BG_FX], 4
    cmp byte [BG_FX], 8
    jb .fx
    inc byte [BG_S]
    cmp byte [BG_S], BZ_BAL_SHIFTS
    jae .q
    mov si, BG_TB               ; TB one pixel right for the next shift
    xor ch, ch
.tbs:
    mov ax, [si]
    mov dx, [si + 2]
    mov cl, [si + 4]
    BG_SH2
    mov [si], ax
    mov [si + 2], dx
    mov [si + 4], cl
    add si, 5
    cmp si, BG_TB + 160
    jb .tbs
    jmp .s
    ; --- Q: frame 0's planes, the base colour where it is clear (the rank
    ; tables are still in place; the squash entries overwrite them)
.q:
    call bg_pz                  ; phase 0's ink as WORDS: P's first word an
    mov si, BZ_BG_XR            ; entry, buckets and their running OR as bg_pb
    mov dx, 8000h
    mov cx, 16
.qx:
    mov bl, [es:si]
    add si, 8
    or [bx + BG_P], dx
    shr dx, 1
    loop .qx
    mov cl, [BG_SC + BZ_BG_NP]
    sub cl, 2
    jz .q0
    mov si, BG_P + BZ_BG_PSTR
    xor ax, ax
.qp:
    or ax, [si]
    mov [si], ax
    add si, BZ_BG_PSTR
    loop .qp
.q0:
    mov si, BZ_BG_YE
    xor bp, bp
.qr:
    mov bl, [es:si]
    inc si
    mov dx, [bx + BG_P]         ; frame 0's ink: the columns XR <= YE
    mov ax, [ds:bp + BG_SC + BZ_BG_CLO]
    mov cx, [ds:bp + BG_SC + BZ_BG_CHI]
    mov di, ax
    xor di, cx
    and dx, di                  ; the ink, tex pixels only
    or ax, dx
    or cx, dx
    mov dx, [ds:bp + BG_SC + BZ_BG_O]
    not dx                      ; clear
    mov di, [BG_BH]
    and di, dx
    or cx, di
    xor dx, di                  ; clear and not rubber's
    or ax, dx
    mov [ds:bp + BG_QLO], ax
    mov [ds:bp + BG_QHI], cx
    inc bp
    inc bp
    cmp bp, 32
    jb .qr
    xor bx, bx
    mov [BG_SS - 2], bx         ; the shape rows' guards
    mov [BG_SS + 32], bx
    ; --- the squash, the shadow, rubber's stretch (the shatter, glass's, is stored)
    mov di, BZ_BAL_SQOFF
    mov si, BG_SC + BZ_BG_SQ0
    call bg_ent
    mov si, BG_SC + BZ_BG_SQ1
    call bg_ent
    call bg_shd
    cmp byte [es:BZB_NSTR], 0
    je .out
    call bg_gatq
    mov di, BZ_BAL_STROFF
    mov si, BG_SC + BZ_BG_STR
    call bg_ent
.out:
    pop es
    pop ax
    ret

; the spread of a nibble n to the odd bits of a byte (n's bit 3 to bit 7 ...)
bg_nib:
    db 00h, 02h, 08h, 0Ah, 20h, 22h, 28h, 2Ah, 80h, 82h, 88h, 8Ah, 0A0h, 0A2h, 0A8h, 0AAh

; bg_pb - the mask table P for phase [BG_FX] at shift [BG_S]: P[k] = the
; columns x whose XR <= k 6 (XR is (R' + 1) 6), each a field of 11 at slot
; x + s; built as buckets (column x ORed into entry XR / 6), then their running
; OR.  BH = 0; uses everything else
bg_pb:
    call bg_pz
    mov al, [BG_FX]
    add ax, BZ_BG_XR            ; column-major: XR[x][fx] at 8 x + fx
    mov si, ax
    mov cl, [BG_S]
    shl cl, 1
    mov al, 0C0h
    shr al, cl                  ; slot s: byte 0
    xor di, di
    mov cx, 16
.x:
    mov bl, [es:si]
    add si, 8
    or [bx + di + BG_P], al
    ror al, 1
    ror al, 1
    adc di, 0                   ; the field wrapped to the next byte
    loop .x
    mov cl, [BG_SC + BZ_BG_NP]
    sub cl, 2                   ; entries 1 .. NP - 2 (the last is a bucket no
    jz .r                       ; row reads)
    mov si, BG_P + BZ_BG_PSTR
    xor ax, ax
    xor dx, dx
    xor bp, bp
.pf:
    or ax, [si]
    mov [si], ax
    or dx, [si + 2]
    mov [si + 2], dx
    or bp, [si + 4]
    mov [si + 4], bp
    add si, BZ_BG_PSTR
    loop .pf
.r:
    ret

; bg_pz - P's NP entries zeroed; AX = 0, CX = 0, DI used
bg_pz:
    push es
    push ds
    pop es
    mov di, BG_P
    xor ax, ax
    mov cl, [BG_SC + BZ_BG_NP]
    xor ch, ch
    mov dx, cx
    add cx, cx
    add cx, dx                  ; NP entries of three words
    rep stosw
    pop es
    ret

; bg_sp - DX = a plane (pixel x in bit 15 - x) -> AX, DX = its pixels as 2-bit
; fields of 11, bytes 0..3 in memory order (AL first).  BH = 0; uses BL, SI
bg_sp:
    mov bl, dh
    mov al, [bx + BG_HH]
    mov ah, [bx + BG_HL]
    mov bl, dl
    mov dl, [bx + BG_HH]
    mov dh, [bx + BG_HL]
    mov si, ax                  ; the odd bits, and again one right (each
    shr si, 1                   ; byte's bit 0 is clear: nothing crosses)
    or ax, si
    mov si, dx
    shr si, 1
    or dx, si
    ret

; bg_il - DX = the high plane, CX = the low -> AX, DX = the 2-bit fields,
; bytes 0..3 in memory order.  BH = 0; uses BL, SI
bg_il:
    mov bl, ch
    mov al, [bx + BG_HH]
    mov ah, [bx + BG_HL]
    shr ax, 1
    mov bl, dh
    or al, [bx + BG_HH]
    or ah, [bx + BG_HL]
    mov si, ax
    mov bl, cl
    mov al, [bx + BG_HH]
    mov ah, [bx + BG_HL]
    shr ax, 1
    mov bl, dl
    or al, [bx + BG_HH]
    or ah, [bx + BG_HL]
    mov dx, ax
    mov ax, si
    ret

; bg_put4 - AX, DX, CL = a row at shift 0 (CL its fifth byte, the fill), CH
; = the fill's field (C0h or 0): the row to ES:DI and its shifts 1..3 to
; ES:DI + BP, + 2 BP, + 3 BP; DI is left + 3 BP.  BH = 0; AX, DX, CL, BL used
bg_put4:
    mov bl, 3
.s:
    mov [es:di], ax
    mov [es:di + 2], dx
    mov [es:di + 4], cl
    add di, bp
    BG_SH2
    dec bl
    jnz .s
    mov [es:di], ax
    mov [es:di + 2], dx
    mov [es:di + 4], cl
    ret

; bg_shape - SI = a shape table (height, then 16 rows of n): the rows' words
; into BG_SS, row y = bits 8 - n .. 7 + n of 16 (0 for n = 0)
bg_shape:
    lodsb
    mov [BG_H], al
    mov bp, BG_SS
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
    mov [ds:bp], ax
    inc bp
    inc bp
    dec dl
    jnz .s
    ret

; bg_ent - an entry (squash 0 or 1, the stretch): SI = its shape table; ES:DI
; gets its four shifts of two identical copies, each (16 mask rows, 16 frame
; rows), and DI is left past it.  Row y of the shape: I = the interior (all
; four neighbours in), the ring = S and not I is BLACK, glass's checker K = I
; and (x + y even) is see-through, so opaque = S xor K and coloured = I xor K;
; the colour of a coloured pixel is the Q pixel at row sy = 15 - ((15 - y) 16)
; / h (h 16, the stretch: y itself - its columns were pressed by bg_gatq).
bg_ent:
    xor bx, bx
    push di
    mov [BG_EDI], di
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
    xor ax, cx                  ; opaque
    xor dx, cx                  ; coloured
    mov [BG_COL], dx
    not ax
    xchg ax, dx
    push bp
    call bg_sp                  ; the mask row: the clear pixels kept
    mov cx, 0C0FFh
    mov di, [BG_EDI]
    mov bp, 2 * BZ_BAL_ENT
    call bg_put4
    pop bp
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
    mov bl, bh
    xor ah, ah
    shl ax, 1
    mov si, ax
    mov dx, [si + BG_QHI]
    and dx, [BG_COL]
    mov cx, [si + BG_QLO]
    and cx, [BG_COL]
    call bg_il                  ; the frame row
    xor cx, cx
    mov di, [BG_EDI]
    add di, BZ_BAL_FRMB
    push bp
    mov bp, 2 * BZ_BAL_ENT
    call bg_put4
    pop bp
    add word [BG_EDI], BZ_BAL_RB
    inc bp
    inc bp
    cmp bp, 32
    jb .y
    pop di                      ; the second copies: each shift's, again
    push ds
    push es
    pop ds
    mov dx, BZ_BAL_SHIFTS
.c:
    mov si, di
    add di, BZ_BAL_ENT
    mov cx, BZ_BAL_ENT / 2
    rep movsw
    dec dx
    jnz .c
    pop ds
    ret

; bg_shd - the shadow masks: parity p, shift s, row r (6): the ellipse's row
; with the world checker (x + s + p + r even) cleared, AND only
bg_shd:
    xor bx, bx
    mov si, BG_SC + BZ_BG_SHD
    call bg_shape
    mov di, BZ_BAL_SHDOFF
    mov [BG_PAR], bh
.p:
    mov [BG_S], bh
.s:
    mov cl, [BG_S]
    add cl, [BG_PAR]
    mov ax, 0AAAAh
    ror ax, cl
    mov [BG_CHK], ax
    xor bp, bp
.r:
    mov dx, [ds:bp + BG_SS]
    and dx, [BG_CHK]
    ror word [BG_CHK], 1
    not dx
    call bg_sp
    mov cx, 0C0FFh
    mov bl, [BG_S]
.k:
    or bl, bl
    jz .put
    BG_SH2
    dec bl
    jmp short .k
.put:
    stosw
    xchg ax, dx
    stosw
    mov al, cl
    stosb
    inc bp
    inc bp
    cmp bp, 2 * BZ_BAL_SHDROWS
    jb .r
    inc byte [BG_S]
    cmp byte [BG_S], BZ_BAL_SHIFTS
    jb .s
    inc byte [BG_PAR]
    cmp byte [BG_PAR], 2
    jb .p
    ret

; bg_gatq - rubber's stretch presses the round frame's COLUMNS: every Q row
; (32 words) is rebuilt with pixel x = the old pixel sx[x] (SX holds sx + 1):
; SN[c] = the pixels x whose sx[x] is c, and a row is the OR of SN[c] over its
; set columns c
BG_SN       equ BG_SS + 34                  ; 16 words
%if 66 + 34 + 32 > BGR_V - BGR_TB
 %error "bz_ballgen: the entries' scratch overlaps the variables"
%endif
bg_gatq:
    push es
    push ds
    pop es
    mov di, BG_SN
    xor ax, ax
    mov cx, 16
    rep stosw
    pop es
    xor bx, bx
    mov si, BG_SC + BZ_BG_SX
    mov dx, 8000h
.sn:
    lodsb
    mov bl, al
    shl bl, 1
    or [bx + BG_SN - 2], dx
    shr dx, 1
    jnz .sn
    mov bp, BG_QLO
.w:
    mov ax, [ds:bp]
    xor dx, dx
    mov si, BG_SN
    jmp short .t
.c:
    shl ax, 1                   ; column c: CF = its pixel
    jnc .n
    or dx, [si]
.n:
    inc si
    inc si
.t:
    or ax, ax                   ; (no more columns set: done)
    jnz .c
    mov [ds:bp], dx
    inc bp
    inc bp
    cmp bp, BG_QLO + 64
    jb .w
    ret
