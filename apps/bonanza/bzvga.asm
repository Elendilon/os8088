; =============================================================================
; apps/bonanza/bzvga.asm - BONANZA's VGA PART, BZVGA.BIN (SPEC.md 128.41)
;
; The VGA's writers and its one-off converter, out of the resident image (which
; has no room for them and whose CGA and Hercules plays never need them): a
; lazy, compressed OP_SEG part, the last row (BZ_P_VGA), fetched on the desktop
; for a VGA play (bz_vprep) and held through the bracket. The shell part's
; shape (SPEC.md 128.19.2), taken whole:
;   1. ITS OWN TABLES THROUGH CS: the conversion tables, the palette's and the
;      sparkles' are read `[cs:...]`; nothing here is WRITTEN through CS, so on
;      kern_mega, where CS is the claim's code alias (op_cseg), it is plain.
;   2. THE PACKAGE THROUGH DS: every vector is entered with DS = ES = the
;      package, and its bss is named by bzlink.inc, which names NO code label.
;   3. IT NEVER CLAIMS: the balls' copies are the package's claim ([bz_vbseg]).
;
; THE MODEL (128.41.3): mode 0Dh, two planes, a stride P of 42 bytes a line
; (CR13 21), the window W = 40 columns of H = 200 one-line rows; the byte of
; world line L, column c is (P L + c) mod 64K in each plane, and S = (P R0 +
; c0) mod 64K. THE ART (128.41.5) is PLANAR PAIRS: eight pixels a word, plane
; 0's byte (bit 7 the leftmost) then plane 1's - converted once, here, at the
; fetch; compose is bitwise, so it runs unchanged, and every writer below only
; splits a word's two bytes into the two planes.
; =============================================================================
cpu 8086
org 0
%include "os88api.inc"
%include "bzcourse.inc"         ; the course tables' macros (identical equates)
%include "bzlink.inc"           ; the package's constants and bss (pxlink)
%include "bzvga.inc"

BZV_P       equ 42              ; the stride, bytes a line (CR13 = 21 words)
BZV_W       equ 40              ; the window's columns (the panning 0: V1)
BZV_H       equ 200             ; ...its rows, a line each
BZV_MLIM    equ 25540           ; 1.5 refreshes, PIT counts (128.41.7)
BZV_LBL     equ 2 * 76          ; bz_latechk's: 18 lines rise to window line 0,
                                ; less the 16 it adds itself (128.41.7)

    dw BZV_SIG0, BZV_SIG1
    dw BZL_IMAGE, BZL_BSS
    times BZV_VEC - ($ - $$) db 0   ; (a negative count fails: the head is BZV_VEC bytes)
    times ($ - $$) - BZV_VEC db 0
bzv_v0: jmp near bzv_conv           ; BZV_CONV (each entered from outside, by far call)
bzv_v1: jmp near bzv_init           ; BZV_INIT
bzv_v2: jmp near bzv_flip           ; BZV_FLIP
bzv_v3: jmp near bzv_pan            ; BZV_PAN
bzv_v4: jmp near bzv_row            ; BZV_ROW
bzv_v5: jmp near bzv_col            ; BZV_COL
bzv_v6: jmp near bzv_boxw           ; BZV_BOXW
bzv_v7: jmp near bzv_blit           ; BZV_BLIT
bzv_v8: jmp near bzv_wprect         ; BZV_WPRECT
bzv_v9: jmp near bzv_card           ; BZV_CARD
    times BZV_VEC + BZV_VECB * BZV_NVEC - ($ - $$) db 0
    times ($ - $$) - BZV_VEC - BZV_VECB * BZV_NVEC db 0

; =============================================================================
; THE CONVERSION TABLES (128.41.5): a CGA byte holds four pixels `hl` from bit
; 7 down. bzv_tl[b] = its four pixels' plane-0 bits (the l's) in the high
; nibble of the low byte and their plane-1 bits (the h's) in the high nibble of
; the high byte - the LEFT four pixels of a planar pair; bzv_tr[b] the same in
; the low nibbles, the RIGHT four. So a CGA word (left byte b0, right b1) is
; the planar pair bzv_tl[b0] | bzv_tr[b1], plane 0's byte first in memory.
; =============================================================================
%macro BZV_NIBS 1               ; %1 = b -> bzv_l, bzv_h: its plane-0, plane-1 nibbles
 %assign bzv_l 0
 %assign bzv_h 0
 %assign bzv_k 0
 %rep 4
  %assign bzv_px ((%1) >> (6 - 2 * bzv_k)) & 3
  %assign bzv_l bzv_l | ((bzv_px & 1) << (3 - bzv_k))
  %assign bzv_h bzv_h | (((bzv_px >> 1) & 1) << (3 - bzv_k))
  %assign bzv_k bzv_k + 1
 %endrep
%endmacro
bzv_tl:
%assign bzv_b 0
%rep 256
 BZV_NIBS bzv_b
            dw (bzv_l << 4) | ((bzv_h << 4) << 8)
 %assign bzv_b bzv_b + 1
%endrep
bzv_tr:
%assign bzv_b 0
%rep 256
 BZV_NIBS bzv_b
            dw bzv_l | (bzv_h << 8)
 %assign bzv_b bzv_b + 1
%endrep

; the CGA's 16 colours as the EGA/VGA attribute controller's 6-bit values (the
; BIOS's mode-0Dh defaults: brown's 14h the one irregular)
bzv_ega16:  db 00h, 01h, 02h, 03h, 04h, 05h, 14h, 07h
            db 38h, 39h, 3Ah, 3Bh, 3Ch, 3Dh, 3Eh, 3Fh
; the wheel's per-card words (bz_wb0 .. bz_warr, SPEC.md 128.12.5.3): the
; rise to window line 0 18 lines (128.41.7), a line 76 PIT counts as the CGA's,
; the refresh 17,025, the word costs the CGA's until bz_wcalib measures them
bzv_wk:     dw 18, 76, 76, 17025, 285, 1000, 300
%if ($ - bzv_wk) != 2 * BZ_WKN
 %error "bz_vinit's per-card words are BZ_WKN"
%endif
; each material's two copies in [bz_vbseg] (bzvga.inc), and its part's size
bzv_cbase:  dw 0, BZV_CR, 2 * BZV_CR, 2 * BZV_CR + BZV_CS
            dw 2 * (BZV_CR + BZV_CS), 2 * (BZV_CR + BZV_CS) + BZV_CG
bzv_bsize:  dw BZ_BAL_SIZER, BZ_BAL_SIZE, BZ_BAL_SIZEG
%if BZ_BAL_ENT != 160 || BZ_BAL_FRMOFF >= BZ_BAL_SQOFF || BZ_BAL_SQOFF >= BZ_BAL_SHDOFF || BZ_BAL_SHDOFF >= BZ_BAL_SHAOFF || BZ_BAL_STROFF != BZ_BAL_SHAOFF
 %error "the ball part's regions (bzconst.inc) are not the converter's (128.41.5)"
%endif

; THE SPARKLES' PLACES (SPEC.md 128.25.19), the VGA's: bzvideo.inc's BZ_SPRS
; places in the same order, each at the eight shifts t = px & 7 - db its byte
; in a ball's box from the sprite's row 0, word 0; dw the planar pair XORed
; there on both lines; dw the next word's (the pair across a word, else 0).
; Off the face both planes (the colour XOR 3), on it plane 0 alone (XOR 1, a
; glint) - the CGA's. The left edge's alternative when (t & 3) + dx < 0, the
; CGA's own rule, so both cards draw one picture
BZV_SPE     equ 5
%macro BZV_SPR 3-5 0, 0         ; dx, dy, face [, alt dx, alt dy]
 %assign bzv_t 0
 %rep 8
  %assign bzv_dx %1
  %assign bzv_dy %2
  %if (bzv_t & 3) + %1 < 0
   %assign bzv_dx %4
   %assign bzv_dy %5
  %endif
  %assign bzv_x bzv_t + bzv_dx
  %assign bzv_m0 (80h >> (bzv_x & 7))
  %assign bzv_m1 0
  %if (bzv_x & 7) < 7
   %assign bzv_m0 bzv_m0 | (bzv_m0 >> 1)
  %else
   %assign bzv_m1 80h
  %endif
  %if bzv_x < 0 || bzv_x + 1 > 23 || bzv_dy > 14
   %error "a sparkle's pair must stay inside the VGA sprite's 3 words and 16 rows"
  %endif
            db bzv_dy * 8 + 2 * (bzv_x >> 3)
  %if %3
            dw bzv_m0, bzv_m1
  %else
            dw bzv_m0 * 101h, bzv_m1 * 101h
  %endif
  %assign bzv_t bzv_t + 1
 %endrep
%endmacro
bzv_spv:    BZV_SPR 0, 0, 0
            BZV_SPR 15, 2, 0
            BZV_SPR 4, 10, 1
            BZV_SPR 14, 0, 0
            BZV_SPR -1, 12, 0, 0, 12
            BZV_SPR 9, 4, 1
            BZV_SPR -1, 2, 0, 0, 2
            BZV_SPR 15, 12, 0
%if $ - bzv_spv != 8 * 8 * BZV_SPE
 %error "eight places, eight shifts"
%endif

; =============================================================================
; BZV_INIT - bz_vinit's VGA half (SPEC.md 128.41.3), after OSAPI_FSX_MODE set
; 0Dh and bz_vinit [bz_vseg]: the geometry, the wheel's words, the camera's
; limits, P*dr, and the card - CR13 21 (P 42), AC 12h 03h (planes 0 and 1),
; AC 0 - 3 the course's four colours, the panning 0.  Preserves nothing.
; =============================================================================
bzv_init:
    mov word [bz_W], BZV_W
    mov word [bz_H], BZV_H
    mov word [bz_rb], BZV_P
    mov word [bz_rl], 1
    mov byte [bz_lsh], 0
    mov word [bz_bend], 0
    mov word [bz_crtc], 3d4h
    mov word [bz_vrport], 3dah
    mov word [bz_vrbits], 0008h ; 3DAh bit 3 HIGH: in the retrace (the CGA's)
    mov word [bz_vrlim], 2
    mov word [bz_mlim], BZV_MLIM
    mov word [bz_lblank], BZV_LBL
    mov word [bz_smask], 0ffffh
    push ds
    pop es
    mov di, bz_wb0
    mov si, bzv_wk
    mov cx, BZ_WKN
.wk:
    cs lodsw
    stosw
    loop .wk
    mov ax, [bz_cols]           ; the camera's limits (128.10.8 item 4)
    sub ax, BZV_W
    mov [bz_cmax], ax
    mov ax, [bz_brows]
    mov cl, 3
    shl ax, cl
    sub ax, BZV_H
    mov [bz_rmax], ax
    mov word [bz_wtab], -2 * BZV_P ; P * dr, dr = -2 .. 2
    mov word [bz_wtab + 2], -BZV_P
    mov word [bz_wtab + 4], 0
    mov word [bz_wtab + 6], BZV_P
    mov word [bz_wtab + 8], 2 * BZV_P
    mov dx, 3d4h                ; CR13: the offset, 21 words
    mov ax, (BZV_P / 2) * 256 + 13h
    out dx, ax
    mov bl, [bz_crs]            ; the course's colour select (128.16.6)...
    xor bh, bh
    add bx, [bz_vcpal]
    mov al, [bx]
    mov ah, al
    and al, 0fh                 ; ...index 0 its background
    mov bx, bzv_ega16
    cs xlat
    mov [bz_vpal0], al
    mov bl, 2                   ; ...1 - 3: palette 0's 2, 4, 6 or 1's 3, 5, 7,
    test ah, 20h                ; each + 8 when bit 4 (intense)
    jz .p0
    inc bx
.p0:
    test ah, 10h
    jz .pi
    add bl, 8
.pi:
    mov cx, 3
    mov di, bz_vpal0 + 1
.pc:
    mov al, bl
    push bx
    mov bx, bzv_ega16
    cs xlat
    pop bx
    stosb
    add bl, 2
    loop .pc
    pushf
    cli
    mov dx, 3dah                ; the attribute flip-flop to its index
    in al, dx
    mov dx, 3c0h
    mov si, bz_vpal0
    xor ah, ah
.ac:
    mov al, ah                  ; AC 0 - 3 (bit 5 clear: the screen off a moment)
    out dx, al
    lodsb
    out dx, al
    inc ah
    cmp ah, 4
    jb .ac
    mov al, 12h                 ; AC 12h: planes 0 and 1 to the glass
    out dx, al
    mov al, 03h
    out dx, al
    mov al, 33h                 ; AC 13h, bit 5 set: the screen on, the panning 0
    out dx, al
    xor al, al
    out dx, al
    popf
    retf

; BZV_FLIP - AX = a start address (bytes) to CR0Ch (high), CR0Dh.  All kept.
bzv_flip:
    push ax
    push cx
    push dx
    mov cx, ax
    mov dx, 3d4h
    mov al, 0ch
    mov ah, ch
    out dx, ax
    mov al, 0dh
    mov ah, cl
    out dx, ax
    pop dx
    pop cx
    pop ax
    retf

; BZV_PAN - AL = the pel panning (0 - 7) to AC 13h, index 33h (the screen on).
; All kept.  bz_tv calls it at the rise, under CLI (128.41.4 rule 4)
bzv_pan:
    push ax
    push dx
    mov ah, al
    mov dx, 3dah
    in al, dx
    mov dx, 3c0h
    mov al, 33h
    out dx, al
    mov al, ah
    out dx, al
    pop dx
    pop ax
    retf

; =============================================================================
; BZV_ROW - bz_row's (SPEC.md 128.41.3): world line AX, world columns BX ..
; BX+CX-1 (CX at least 1), each cell's line word from the course - the map
; entry (map[L>>3][c]) + 2 (L&7) - plane 0's byte to plane 0, plane 1's to
; plane 1, at (P L + c) mod 64K.  Whether a row goes into the slack (128.41.4
; rule 1) or the full write, its order is free.  All kept.
; =============================================================================
bzv_row:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    push ds
    push es
    mov es, [bz_vseg]
    mov si, ax                  ; SI = L
    mov dx, BZV_P
    mul dx
    add ax, bx
    mov di, ax                  ; DI = P L + c0 (mod 64K)
    mov ax, si
    and al, 0f8h
    push cx
    mov cl, [bz_mapsh]
    shl ax, cl
    pop cx
    shl bx, 1
    add ax, bx
    add ax, BZC_MAP             ; AX = the first cell's map entry
    and si, 7
    shl si, 1
    mov bp, si                  ; BP = the line's word in a block
    mov ds, [bz_mseg]           ; DS = the course's PICTURE part
    mov si, ax
    mov dx, 3c4h
    push si
    push di
    push cx
    mov ax, 0102h               ; plane 0
    out dx, ax
.p0:
    lodsw
    add ax, bp
    mov bx, ax
    mov al, [bx]
    stosb
    loop .p0
    pop cx
    pop di
    pop si
    mov ax, 0202h               ; plane 1
    out dx, ax
    inc bp
.p1:
    lodsw
    add ax, bp
    mov bx, ax
    mov al, [bx]
    stosb
    loop .p1
    pop es
    pop ds
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    retf

; =============================================================================
; BZV_COL - the entering column [bz_ccol], every line of the NEW window
; ([bz_R0n] on, BZV_H of them), before the start address (128.41.4 rule 1):
; the gutter's cells, off the glass.  A plane at a time, a block's lines from
; one map entry.  Preserves nothing (DS, ES the package's again).
; =============================================================================
bzv_col:
    mov es, [bz_vseg]
    mov ax, [bz_R0n]            ; L
    mov bx, [bz_ccol]
    push ax
    mov dx, BZV_P
    mul dx
    add ax, bx
    mov di, ax                  ; DI = P L + c
    pop ax
    mov dx, ax
    and dx, 7                   ; DL = j, the first line's in its block
    and al, 0f8h
    mov cl, [bz_mapsh]
    shl ax, cl
    shl bx, 1
    add ax, bx
    add ax, BZC_MAP
    mov si, ax                  ; SI = its map entry
    mov bp, 8
    shl bp, cl                  ; BP = a block row's map bytes
    push ds
    mov ds, [bz_mseg]
    mov ax, 0102h
    xor dh, dh                  ; DH = the plane's byte
    call .plane
    mov ax, 0202h
    inc dh
    call .plane
    pop ds
    push ds
    pop es
    retf
.plane:                         ; AX = the map mask, DL = j, DH = the plane
    push si
    push di
    push dx
    push dx
    mov dx, 3c4h
    out dx, ax
    pop dx
    mov cx, BZV_H
.blk:
    mov bx, [si]                ; the block
    mov al, dh
    xor ah, ah
    add bx, ax
    mov al, dl
    shl ax, 1
    add bx, ax                  ; BX = its line j's byte of the plane
.ln:
    mov al, [bx]
    stosb
    add di, BZV_P - 1
    inc bx
    inc bx
    dec cx
    jz .done
    inc dl
    cmp dl, 8
    jb .ln
    xor dl, dl
    add si, bp
    jmp short .blk
.done:
    pop dx
    pop di
    pop si
    ret

; =============================================================================
; BZV_BOXW - box SI (a descriptor: +0 x0 world column, +2 y0 world line, +4 w
; words, +6 h lines, +8 the buffer, 8 bytes a line) to the card, a line at a
; time in raster order (128.41.4 rule 5): each line's even bytes to plane 0,
; its odd to plane 1 - no conversion (128.41.5).  A later box overlapping an
; earlier one writes the same bytes again (the CGA's band skip is a saving,
; not a rule).  ONE BODY A WIDTH (1 - 4 words), unrolled: per line the map
; mask twice and a `movsb` / `inc si` a byte, the buffer's and the card's
; steps folded into four adds (V1's measure: 785 clocks a line looped, the
; bar 500).  All kept.
; =============================================================================
%macro BZV_BWL 1                ; a line of %1 words, the loop round its box
.w%1:
    mov ax, 0102h
    out dx, ax
 %rep %1
    movsb
    inc si
 %endrep
    sub si, 2 * %1 - 1          ; back to the line's first odd byte
    sub di, %1
    mov ax, 0202h
    out dx, ax
 %rep %1
    movsb
    inc si
 %endrep
 %if 8 - 2 * %1 - 1 == -1
    dec si
 %else
    add si, 8 - 2 * %1 - 1      ; the buffer's next line
 %endif
    add di, BZV_P - %1          ; the card's
    dec bp
    jnz .w%1
    jmp .done
%endmacro
bzv_boxw:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    push es
    mov es, [bz_vseg]
    mov ax, [si + 2]
    mov dx, BZV_P
    mul dx
    add ax, [si]
    mov di, ax                  ; DI = the box's first byte on the card
    mov bx, [si + 4]            ; BX = w
    mov bp, [si + 6]            ; BP = h
    mov si, [si + 8]            ; SI = the buffer
    mov dx, 3c4h
    or bp, bp
    jz .done
    dec bx
    cmp bx, 3
    ja .done                    ; (w 1 - 4: a box is BZ_BOXW words at most)
    shl bx, 1
    jmp [cs:.wtab + bx]
.wtab:      dw .w1, .w2, .w3, .w4
    BZV_BWL 1
    BZV_BWL 2
    BZV_BWL 3
    BZV_BWL 4
.done:
    pop es
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    retf

; =============================================================================
; BZV_BLIT - bz_blit's (SPEC.md 128.41.5): a sprite of the ball part into box
; SI, clipped to it - rows i at world lines AX + i, i < DX; MASK row 0 at DI
; and the FRAME BX past it, both offsets into the CGA ball part (bz_sprite's,
; bz_boxc's); BX = 0 no frame (the shadow: AND only); BX bit 15 the pickup
; CUE's look, the sprite whole in the box (its sparkles).  The VGA's sprite is
; the converted COPY (px & 4) / 4 of the material's, a row three words placed
; at the world word px >> 3; an offset o becomes 16 + (o - 16) 6 / 5.  While
; the dissolve's copies stand in ([bz_bseg] is the package, bzphys.inc
; bz_fdis) they are the CGA's rows, and each word is converted as it is laid -
; only then.  Keeps SI, DS, ES; clobbers AX, BX, CX, DX, DI, BP.
; =============================================================================
bzv_blit:
    push si
    mov [bz_bly], ax
    mov [bz_blm], di
    mov bp, bx                  ; BP = the flags' and the distance
    and bx, 7fffh
    ; rows i in [imin, imax): AX + i inside [y0, y0 + h)
    mov cx, [si + 2]
    sub cx, ax
    jge .imin
    xor cx, cx
.imin:
    mov [bz_imin], cx
    mov ax, [si + 2]
    add ax, [si + 6]
    sub ax, [bz_bly]
    cmp ax, dx
    jle .imax
    mov ax, dx
.imax:
    sub ax, cx
    jg .rows
    jmp .out
.rows:
    push dx                     ; (the sprite's rows: the whole test)
    mov dx, ax                  ; DX = the rows laid
    ; words k in [kmin, kmax) of three: px/8 + k inside [x0, x0 + w)
    mov cx, [bz_px]
    shr cx, 1
    shr cx, 1
    shr cx, 1                   ; CX = the sprite's first world word
    mov ax, [si]
    sub ax, cx
    jge .kmin
    xor ax, ax
.kmin:
    mov [bz_kmin], ax
    mov ax, [si]
    add ax, [si + 4]
    sub ax, cx
    cmp ax, 3
    jle .kmax
    mov ax, 3
.kmax:
    sub ax, [bz_kmin]
    jg .words
    pop ax
    jmp .out
.words:
    mov [bz_bw], ax             ; the words a row
    ; the destination: buf + (y + imin - y0) 8 + 2 (px/8 + kmin - x0)
    mov di, [bz_bly]
    add di, [bz_imin]
    sub di, [si + 2]
    shl di, 1
    shl di, 1
    shl di, 1
    add di, [si + 8]
    add cx, [bz_kmin]
    sub cx, [si]
    shl cx, 1
    add di, cx                  ; DI = the first word laid, ES = ours
    pop ax                      ; AX = the sprite's rows
    push di                     ; (the whole sprite's row 0, word 0 when it is
    cmp dx, ax                  ;  whole: the sparkles)
    jne .nw
    cmp word [bz_bw], 3
    je .wh
.nw:
    and bp, 7fffh               ; (clipped: no sparkles, as the CGA)
.wh:
    mov ax, [bz_bseg]
    mov cx, ds
    cmp ax, cx
    jne .copy
    jmp .conv
.copy:
    ; the converted copy: its base + 16 + (o - 16) / 5 * 6, the frame BX / 5 * 6
    push dx                     ; (the rows laid)
    mov ax, [bz_blm]
    sub ax, 16
    xor dx, dx
    mov cx, 5
    div cx
    mov cx, ax
    shl ax, 1
    add ax, cx
    shl ax, 1                   ; 6 (o - 16) / 5
    add ax, 16
    mov si, ax
    mov ax, bx
    xor dx, dx
    mov cx, 5
    div cx
    mov bx, ax
    shl ax, 1
    add bx, ax
    shl bx, 1                   ; BX = the frame's distance, 6-byte rows
    mov al, [bz_mat]
    xor ah, ah
    shl ax, 1
    shl ax, 1                   ; 4 m: the material's pair in bzv_cbase
    test byte [bz_px], 4
    jz .c0
    inc ax
    inc ax                      ; ...its copy 1
.c0:
    xchg ax, bx
    mov bx, [cs:bzv_cbase + bx]
    xchg ax, bx
    add si, ax                  ; SI = mask row 0 in [bz_vbseg]
    mov ax, [bz_imin]           ; ...row imin, word kmin
    mov cx, ax
    shl ax, 1
    add ax, cx
    shl ax, 1
    add si, ax
    mov ax, [bz_kmin]
    shl ax, 1
    add si, ax
    pop dx
    mov cx, [bz_bw]
    push ds
    mov ds, [bz_vbseg]
    or bx, bx
    jz .sh
.r:                             ; mask AND, frame OR
    push si
    push di
    push cx
.w:
    lodsw
    and ax, [es:di]
    or ax, [bx + si - 2]
    stosw
    loop .w
    pop cx
    pop di
    pop si
    add si, 6
    add di, 8
    dec dx
    jnz .r
    jmp short .laid
.sh:                            ; the shadow: AND alone
    push si
    push di
    push cx
.sw:
    lodsw
    and ax, [es:di]
    stosw
    loop .sw
    pop cx
    pop di
    pop si
    add si, 6
    add di, 8
    dec dx
    jnz .sh
.laid:
    pop ds
    jmp .spark

; THE DISSOLVE's copies, CGA rows of 5 bytes in the package ([bz_blm] the
; mask's row 0, BX on to the frame's): each word of copy (px & 4) / 4 made
; from them as it is laid - copy 0's words are bytes (0,1), (2,3), (4, pad),
; copy 1's (pad, 0), (1,2), (3,4); a mask's pad keeps (FFh), a frame's is 0
.conv:
    mov si, [bz_blm]
    mov ax, [bz_imin]
    mov cx, ax
    shl ax, 1
    shl ax, 1
    add ax, cx
    add si, ax                  ; SI = row imin's first byte (5 a row)
    mov cx, [bz_bw]
.cr:
    push si
    push di
    push cx
    mov cx, [bz_kmin]           ; CX = k
.cw:
    push bx
    mov ah, 0ffh                ; the mask's word k
    call .cword
    and [es:di], ax
    pop bx
    or bx, bx
    jz .cn
    push bx
    push si
    add si, bx
    xor ah, ah                  ; ...the frame's
    call .cword
    pop si
    pop bx
    or [es:di], ax
.cn:
    inc di
    inc di
    inc cx
    pop ax
    push ax                     ; (the words a row)
    add ax, [bz_kmin]
    cmp cx, ax
    jb .cw
    pop cx
    pop di
    pop si
    add si, 5
    add di, 8
    dec dx
    jnz .cr
    jmp short .spark
; .cword - SI = a CGA row, CX = k (0 - 2), AH = the pad -> AX = word k of the
; copy [bz_px] & 4 says, a planar pair.  Clobbers BX
.cword:
    push dx
    mov dl, ah                  ; DL = the pad
    mov bx, cx
    shl bx, 1                   ; 2 k
    test byte [bz_px], 4
    jnz .cw1
    mov al, [si + bx]           ; copy 0: bytes 2k, 2k + 1 (byte 5 the pad)
    cmp bx, 4
    mov ah, dl
    je .cpair
    mov ah, [si + bx + 1]
    jmp short .cpair
.cw1:
    mov al, dl                  ; copy 1: bytes 2k - 1 (byte -1 the pad), 2k
    or bx, bx
    jz .cw1b
    mov al, [si + bx - 1]
.cw1b:
    mov ah, [si + bx]
.cpair:
    mov dl, ah                  ; the pair: bzv_tl[AL] | bzv_tr[AH]
    xor bh, bh
    mov bl, al
    shl bx, 1
    mov ax, [cs:bzv_tl + bx]
    mov bl, dl
    xor bh, bh
    shl bx, 1
    or ax, [cs:bzv_tr + bx]
    pop dx
    ret

; THE CUE's SPARKLES (SPEC.md 128.25.19): the whole sprite only (BP bit 15
; kept), with BZ_CL_SP in the look - each of the three sparkles' place
; ([bz_spq]: a pointer into bzvideo.inc's CGA table, BZ_SPRP bytes a place)
; at shift px & 7 from bzv_spv, XORed on its two lines after the ball
.spark:
    pop di                      ; DI = the sprite's row 0, word 0 in the box
    or bp, bp
    jns .out
    test byte [bz_clook], BZ_CL_SP
    jz .out
    mov cx, 3
    mov si, bz_spq
.sp:
    lodsw
    sub ax, [bz_vspr0]
    xor dx, dx
    mov bx, BZ_SPRP
    div bx                      ; AX = the place
    shl ax, 1
    shl ax, 1
    shl ax, 1                   ; 8 place
    mov bl, [bz_px]
    and bx, 7
    add ax, bx                  ; + t
    mov bx, ax
    shl ax, 1
    shl ax, 1
    add bx, ax                  ; 5 (8 place + t)
    add bx, bzv_spv
    mov al, [cs:bx]
    xor ah, ah
    push di
    add di, ax
    mov ax, [cs:bx + 1]
    xor [es:di], ax
    xor [es:di + 8], ax
    mov ax, [cs:bx + 3]
    xor [es:di + 2], ax
    xor [es:di + 10], ax
    pop di
    loop .sp
    jmp short .out
.out:
    pop si
    retf

; =============================================================================
; BZV_WPRECT - bz_wprect's (bzwheel.inc, SPEC.md 128.12.5): rectangle SI (card
; rows - lines here - [r0, r1), words [x0, x1)) of the lane whose pose is at
; [bz_lsrc] (row stride [bz_lsst]; the lane's first block row [bz_lbr], first
; word column [bz_lcl]), column by column: each block's pose word into the
; map, then that block's lines inside [r0, r1) to the card, a plane at a time.
; No ring end to cross (128.41.3).  DS = ES = ours on entry and on the way
; out; clobbers AX - DI, BP.
; =============================================================================
bzv_wprect:
    mov cx, [si + 2]
    sub cx, [si]
    jle .x
    mov ax, [si + 6]
    sub ax, [si + 4]
    jg .go
.x:
    retf
.go:
    mov [bz_vwr0], cx           ; (the rows: a frame of locals in our bss)
    mov ax, [si]
    mov [bz_vwr0], ax           ; r0
    mov ax, [si + 2]
    mov [bz_vwr1], ax           ; r1
    mov ax, [si + 4]
    mov [bz_vwx], ax            ; x, from x0
    mov ax, [si + 6]
    mov [bz_vwx1], ax           ; x1
    mov es, [bz_vseg]
.col:
    mov ax, [bz_vwr0]
    mov cl, 3
    shr ax, cl
    mov [bz_vwbr], ax           ; br, from r0's block row
.blk:
    ; the pose: [lsrc + (br - lbr) lsst + 2 (x - lcl)], into the map entry
    mov ax, [bz_vwbr]
    sub ax, [bz_lbr]
    mul word [bz_lsst]
    add ax, [bz_lsrc]
    mov si, [bz_vwx]
    sub si, [bz_lcl]
    shl si, 1
    add si, ax
    mov ax, [bz_vwbr]           ; the map entry: BZC_MAP + (8 br << mapsh) + 2 x
    mov cl, 3
    shl ax, cl
    mov cl, [bz_mapsh]
    shl ax, cl
    add ax, [bz_vwx]
    add ax, [bz_vwx]
    add ax, BZC_MAP
    mov di, ax
    push ds
    mov ds, [bz_mseg]           ; (the PICTURE part: the poses, the map, the blocks)
    mov si, [si]
    mov [di], si                ; SI = the block, into the map
    pop ds
    ; its lines [max(r0, 8 br), min(r1, 8 br + 8))
    mov ax, [bz_vwbr]
    mov cl, 3
    shl ax, cl
    mov bx, ax                  ; BX = 8 br
    mov dx, ax
    add dx, 8                   ; DX = 8 br + 8
    cmp ax, [bz_vwr0]
    jge .l0
    mov ax, [bz_vwr0]
.l0:
    cmp dx, [bz_vwr1]
    jle .l1
    mov dx, [bz_vwr1]
.l1:
    sub dx, ax                  ; DX = the lines
    jle .nb
    sub bx, ax
    neg bx
    shl bx, 1
    add si, bx                  ; SI = the first line's word in the block
    push dx
    mov dx, BZV_P
    mul dx
    add ax, [bz_vwx]
    mov di, ax                  ; DI = P L + x
    pop cx                      ; CX = the lines
    push ds
    mov ds, [bz_mseg]
    mov bp, 0102h
    call .pl
    inc si
    mov bp, 0202h
    call .pl
    pop ds
.nb:
    inc word [bz_vwbr]
    mov ax, [bz_vwbr]
    mov cl, 3
    shl ax, cl
    cmp ax, [bz_vwr1]
    jl .blk
    inc word [bz_vwx]
    mov ax, [bz_vwx]
    cmp ax, [bz_vwx1]
    jl .col
    push ds
    pop es
    retf
.pl:                            ; BP = the map mask, CX lines from SI to DI on
    push cx                     ; (a plane's bytes, a word apart)
    push si
    push di
    mov ax, bp
    mov dx, 3c4h
    out dx, ax
.pll:
    movsb
    inc si
    add di, BZV_P - 1
    loop .pll
    pop di
    pop si
    pop cx
    ret

; BZV_CARD - bzcard.inc's cell on the VGA (SPEC.md 128.41.4): AX = the CGA's
; word for it (colour 3 on 0: each pixel's pair 11 or 00), DX = the cell, BP =
; the card's line - the planar pair to (P (crdy0 + BP) + S + crdc0 + DX) mod
; 64K, a byte a plane.  ES = the card.  All kept
bzv_card:
    push ax
    push bx
    push dx
    push di
    mov bl, al                  ; the pair, through the tables
    xor bh, bh
    shl bx, 1
    push word [cs:bzv_tl + bx]
    mov bl, ah
    xor bh, bh
    shl bx, 1
    mov bx, [cs:bzv_tr + bx]
    pop ax
    or bx, ax                   ; BX = the planar pair
    mov di, dx
    add di, [bz_S]
    add di, [bz_crdc0]
    mov ax, [bz_crdy0]
    add ax, bp
    mov dx, BZV_P
    mul dx
    add di, ax                  ; DI = the cell's byte
    mov dx, 3c4h
    mov ax, 0102h
    out dx, ax
    mov [es:di], bl
    mov ax, 0202h
    out dx, ax
    mov [es:di], bh
    pop di
    pop dx
    pop bx
    pop ax
    retf

; =============================================================================
; BZV_CONV - THE ART, CONVERTED ONCE (SPEC.md 128.41.5), at the end of every
; bz_cload: the course's blocks and occluder masks (the PICTURE part) and the
; platform slabs' sprites (the WORLD part) word for word in place - not a HELD
; pathway's, converted when it was fetched ([bz_phre]) - and the three balls,
; each into its two copies in [bz_vbseg], unless the copies there are of the
; same three parts already (their segments kept in the claim's first six
; bytes, rubber copy 0's head, which no blit reads).  Preserves nothing.
; =============================================================================
bzv_conv:
    cmp byte [bz_phre], 0
    jne .balls
    mov es, [bz_mseg]
    mov si, [es:BZC_BLKOFF]
    mov cx, [es:BZC_NBLK]
    shl cx, 1
    shl cx, 1
    shl cx, 1                   ; 8 words a block
    call .words
    mov si, [es:BZC_MASKOFF]
    mov cx, [es:BZC_NMASK]
    shl cx, 1
    shl cx, 1
    shl cx, 1
    call .words
    mov es, [bz_cseg]
    mov cx, [es:BZC_NPROP]
    mov di, [es:BZC_PROPOFF]
    jcxz .balls
.pr:
    cmp byte [es:di + BZP_KIND], BZ_PK_PLATFORM
    jne .pn
    push cx
    mov si, [es:di + BZP_PSPR]
    mov cx, BZ_PLSPR / 2
    call .words
    pop cx
.pn:
    add di, BZ_PROPREC
    loop .pr
.balls:
    mov es, [bz_vbseg]
    mov ax, [bz_bsegs]
    cmp ax, [es:0]
    jne .bdo
    mov ax, [bz_bsegs + 2]
    cmp ax, [es:2]
    jne .bdo
    mov ax, [bz_bsegs + 4]
    cmp ax, [es:4]
    je .done
.bdo:
    xor bx, bx                  ; BX = 2 m
.ball:
    push bx
    call .one
    pop bx
    inc bx
    inc bx
    cmp bx, 2 * BZ_NMAT
    jb .ball
    mov ax, [bz_bsegs]          ; (which parts the copies are of)
    mov [es:0], ax
    mov ax, [bz_bsegs + 2]
    mov [es:2], ax
    mov ax, [bz_bsegs + 4]
    mov [es:4], ax
.done:
    push ds
    pop es
    retf
; ES:SI, CX words (at least 1) converted in place.  Clobbers AX, BX, CX, SI
.words:
    jcxz .wx
.wl:
    mov bl, [es:si]
    xor bh, bh
    shl bx, 1
    mov ax, [cs:bzv_tl + bx]
    mov bl, [es:si + 1]
    xor bh, bh
    shl bx, 1
    or ax, [cs:bzv_tr + bx]
    mov [es:si], ax
    inc si
    inc si
    loop .wl
.wx:
    ret
; ball 2m: [bz_bsegs + 2m]'s rows, 5 bytes from 16, into its two copies -
; each row's pad by its region (a mask's keeps, a frame's is 0; an entry's
; mask half then its frame half, BZ_BAL_ENT bytes).  ES = [bz_vbseg].
.one:
    mov ax, [cs:bzv_bsize + bx]
    mov [bz_vwx1], ax           ; the part's size
    shl bx, 1
    mov di, [cs:bzv_cbase + bx] ; DI = copy 0's
    mov bp, [cs:bzv_cbase + bx + 2]
    sub bp, di                  ; BP = copy 1 - copy 0
    shr bx, 1
    push ds
    mov ax, [bz_bsegs + bx]
    mov [bz_vwx], ax
    pop ds
    add di, 16
    mov si, 16                  ; SI = the row's offset in the part
.row:
    cmp si, [bz_vwx1]
    jae .ox
    call .pad                   ; DL = the row's pad
    push ds
    mov ds, [bz_vwx]
    mov al, [si]                ; copy 0: (b0, b1), (b2, b3), (b4, pad)
    mov ah, [si + 1]
    call .pair
    mov [es:di], ax
    mov al, [si + 2]
    mov ah, [si + 3]
    call .pair
    mov [es:di + 2], ax
    mov al, [si + 4]
    mov ah, dl
    call .pair
    mov [es:di + 4], ax
    mov al, dl                  ; copy 1: (pad, b0), (b1, b2), (b3, b4)
    mov ah, [si]
    call .pair
    mov [es:bp + di], ax
    mov al, [si + 1]
    mov ah, [si + 2]
    call .pair
    mov [es:bp + di + 2], ax
    mov al, [si + 3]
    mov ah, [si + 4]
    call .pair
    mov [es:bp + di + 4], ax
    pop ds
    add si, 5
    add di, 6
    jmp short .row
.ox:
    ret
; AL, AH = a CGA word's bytes -> AX = its planar pair.  Clobbers BX
.pair:
    push dx
    mov dl, ah
    mov bl, al
    xor bh, bh
    shl bx, 1
    mov ax, [cs:bzv_tl + bx]
    mov bl, dl
    xor bh, bh
    shl bx, 1
    or ax, [cs:bzv_tr + bx]
    pop dx
    ret
; SI = a row's offset -> DL = its pad: FFh a mask's row, 0 a frame's
.pad:
    push ax
    push bx
    mov dl, 0ffh
    cmp si, BZ_BAL_FRMOFF       ; the masks
    jb .px
    xor dl, dl
    cmp si, BZ_BAL_SQOFF        ; the roll frames
    jb .px
    mov ax, si
    mov bx, BZ_BAL_SQOFF
    cmp si, BZ_BAL_SHDOFF       ; squash entries
    jb .ent
    mov dl, 0ffh
    cmp si, BZ_BAL_SHAOFF       ; the shadow's masks
    jb .px
    mov bx, BZ_BAL_SHAOFF       ; shatter or stretch entries
.ent:
    sub ax, bx
    push dx
    xor dx, dx
    mov bx, BZ_BAL_ENT
    div bx                      ; DX = the place in its entry
    cmp dx, BZ_BAL_ENT / 2
    pop dx
    mov dl, 0ffh
    jb .px
    xor dl, dl
.px:
    pop bx
    pop ax
    ret
