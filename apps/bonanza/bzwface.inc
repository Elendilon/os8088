;;; =============================================================================
;;; apps/bonanza/bzwface.inc - BONANZA's PLAYER FACE (SPEC.md 137.26.1, 137.26.2),
;;; assembled into the SHELL PART beside the instruments' face (bzface.inc), which
;;; paints instead while the harness byte bz_dev is set (137.26.6).
;;;
;;; The window: the title centred near the top, the ledge with the rubber marble
;;; on its right running off the content's right edge, and - the RESIDENT's,
;;; drawn after this returns - the Play Game button at the bottom centre, in
;;; front of the ledge.  Every pixel once: each picture is BLIT1'd (from the
;;; part, through CS) and every other pixel is ONE fill; the ledge's rows that
;;; the button covers are blitted around it, the slice right of the button
;;; shifted into the package's bss first (bz_font: the cards' glyphs, loaded
;;; afresh at every bracket, free on the desktop).  The button's rect is the
;;; resident's (bz_bplace, before the part is called), and so is [bz_wtall].
;;; =============================================================================

; the pictures: data, then a descriptor each - +0 the rows, +2 w, +4 h, +6 bytes
; a row - SHORT then TALL
bzw_d_ts: BZW_TITLE_S_DATA
bzw_d_ls: BZW_LEDGE_S_DATA
bzw_d_tt: BZW_TITLE_T_DATA
bzw_d_lt: BZW_LEDGE_T_DATA
bzw_pics:
    dw bzw_d_ts, BZW_TITLE_S_W, BZW_TITLE_S_H, BZW_TITLE_S_B
    dw bzw_d_ls, BZW_LEDGE_S_W, BZW_LEDGE_S_H, BZW_LEDGE_S_B
    dw bzw_d_tt, BZW_TITLE_T_W, BZW_TITLE_T_H, BZW_TITLE_T_B
    dw bzw_d_lt, BZW_LEDGE_T_W, BZW_LEDGE_T_H, BZW_LEDGE_T_B
%if BZW_TITLE_S_W != BZW_TITLE_T_W || BZW_LEDGE_S_W != BZW_LEDGE_T_W || BZW_LEDGE_S_B * 16 > 512
 %error "bzwface: the two aspects share widths, and a button's rows of the ledge fit bz_font"
%endif
BZW_TTOP_S  equ 4               ; the title's top line, SHORT / TALL
BZW_TTOP_T  equ 8
; (the ledge's bottom margin, BZW_LBOT_S / _T, is bzshell.inc's: the button sits by it)

; bz_wface - the whole content box, at a paint (the clip the kernel's).
; Preserves nothing.
bz_wface:
    call bz_fgeom
    jc .out
    mov bx, bzw_pics            ; SI = the title's descriptor, DI = the ledge's
    mov ax, BZW_TTOP_S
    mov dx, BZW_LBOT_S
    cmp byte [bz_wtall], 0
    je .a
    add bx, 16
    mov ax, BZW_TTOP_T
    mov dx, BZW_LBOT_T
.a:
    mov si, bx
    lea di, [bx + 8]
    mov [bz_wty], ax
    ; the ledge's place: its right edge on the content's, its foot DX up
    mov ax, [bz_fw]             ; (rounded UP to a screen byte: its last few
    sub ax, [cs:di + 2]         ; columns fall past the content's edge and
    add ax, [bz_ox]             ; are not drawn, bzw_blitsl)
    add ax, 7
    and ax, 0fff8h
    sub ax, [bz_ox]
    mov [bz_wlx], ax
    mov ax, [bz_fh]
    sub ax, dx
    sub ax, [cs:di + 4]
    mov [bz_wly], ax
    ; the title's: centred, on a SCREEN BYTE - every picture here is put down
    ; at a byte's start: an unaligned OSAPI_GFX_BLIT1 wraps its first partial
    ; column onto the end of the row (seen on MartyPC's CGA, 2026-11-16)
    mov ax, [bz_fw]
    sub ax, [cs:si + 2]
    sar ax, 1
    add ax, [bz_ox]
    and ax, 0fff8h
    sub ax, [bz_ox]
    mov [bz_wtx], ax
    ; the button, content-relative (bz_btr: SCREEN, inclusive)
    mov ax, [bz_btr]
    sub ax, [bz_ox]
    mov [bz_wbx0], ax
    mov ax, [bz_btr + 4]
    sub ax, [bz_ox]
    mov [bz_wbx1], ax
    mov ax, [bz_btr + 2]
    sub ax, [bz_oy]
    mov [bz_wby0], ax
    mov ax, [bz_btr + 6]
    sub ax, [bz_oy]
    mov [bz_wby1], ax

    ; 1. above the title
    xor bx, bx
    mov dx, [bz_wty]
    dec dx
    call bzw_fillw
    ; 2. the title's rows: its left, it, its right
    mov bx, [bz_wty]
    mov [bz_wy], bx
    mov ax, [cs:si + 4]
    mov [bz_wh], ax
    mov ax, [bz_wtx]
    call bzw_rowpic             ; (SI = the title)
    ; 3. a refusal's reason, under it
    mov ax, [bz_wty]
    add ax, [cs:si + 4]
    mov [bz_wy], ax
    call bzw_reason             ; [bz_wy] stepped past it, when there is one
    ; 4. the keys, centred in what is left above the ledge (SPEC.md 137.26.9)
    call bzw_keys
    ; 5. down to the ledge
    mov bx, [bz_wy]
    mov dx, [bz_wly]
    dec dx
    call bzw_fillw
    ; 6. the ledge's rows: above the button, the button's, below it
    mov si, di
    mov bx, [bz_wly]            ; rows [wly, wby0)
    mov [bz_wy], bx
    mov cx, [bz_wkb]            ; ...the first of them the KEYS' rows too (their
    sub cx, bx                  ; lines filled left of the ledge, bzw_keys):
    jle .own                    ; the picture alone there
    mov [bz_wh], cx
    push cx
    xor bx, bx
    call bzw_bandptr
    mov ax, [bz_wlx]
    mov cx, [cs:si + 2]
    call bzw_blitsl
    pop cx
    add [bz_wy], cx             ; CX = the picture's next row
    jmp short .rest
.own:
    xor cx, cx                  ; (from the picture's row 0)
.rest:
    mov ax, [bz_wby0]
    sub ax, [bz_wy]
    jle .mid
    mov [bz_wh], ax
    mov ax, [bz_wlx]
    call bzw_rowpicr
.mid:
    mov ax, [bz_wby1]           ; rows [wby0, wby1]
    inc ax
    sub ax, [bz_wby0]
    jle .low
    cmp word [bz_wbn], 0        ; (no button: the ledge whole)
    je .low
    call bzw_ledmid
.low:
    mov bx, [bz_wby1]           ; rows (wby1, wly + h)
    inc bx
    cmp word [bz_wbn], 0
    jne .lw
    mov bx, [bz_wly]
.lw:
    cmp bx, [bz_wly]
    jge .lw2
    mov bx, [bz_wly]
.lw2:
    mov [bz_wy], bx
    mov ax, [bz_wly]
    add ax, [cs:si + 4]
    sub ax, bx
    jle .foot
    mov [bz_wh], ax
    mov cx, bx
    sub cx, [bz_wly]            ; the picture's first row
    mov ax, [bz_wlx]
    call bzw_rowpicr
.foot:
    ; 7. under the ledge, to the content's foot
    mov bx, [bz_wly]
    add bx, [cs:si + 4]
    mov dx, [bz_fh]
    dec dx
    call bzw_fillw
.out:
    ret

; the ledge's rows the button covers: [0, min(bx0, lx)) filled, the ledge left
; of the button (when it starts there), the button skipped, then the ledge's
; slice right of it (shifted: its first column is not a byte's) or a fill and
; the whole ledge.  SI = the ledge.
bzw_ledmid:
    mov ax, [bz_wby0]
    mov [bz_wy], ax
    mov ax, [bz_wby1]
    inc ax
    sub ax, [bz_wby0]
    mov [bz_wh], ax
    ; the left: [0, min(bx0, lx)) a fill
    mov cx, [bz_wbx0]
    cmp cx, [bz_wlx]
    jle .l1
    mov cx, [bz_wlx]
.l1:
    xor ax, ax
    dec cx
    call bzw_fillh              ; [AX, CX] over the band's rows
    ; ...the ledge left of the button: [lx, bx0), from column 0
    mov ax, [bz_wlx]
    mov cx, [bz_wbx0]
    sub cx, ax                  ; CX = its width
    jle .right
    push cx
    mov bx, [bz_wy]
    sub bx, [bz_wly]            ; the picture's row
    call bzw_bandptr            ; ES:BP... -> registers for BLIT1 (below)
    pop cx
    call bzw_blitsl             ; AX = content x, CX = width, from column 0
.right:
    mov ax, [bz_wbx1]
    inc ax                      ; AX = the first column right of the button
    cmp ax, [bz_wlx]
    jg .shift
    ; the ledge starts right of the button: a fill, then the ledge whole
    mov cx, [bz_wlx]
    dec cx
    call bzw_fillh
    mov ax, [bz_wlx]
    mov cx, [cs:si + 2]
    mov bx, [bz_wy]
    sub bx, [bz_wly]
    call bzw_bandptr
    jmp bzw_blitsl
.shift:
    ; from the first screen byte at or right of the button: the columns
    ; between filled, then column c = that - lx of the picture to the content's
    ; edge, shifted into bz_font
    push ax
    add ax, [bz_ox]
    add ax, 7
    and ax, 0fff8h
    sub ax, [bz_ox]
    mov cx, ax
    dec cx
    pop dx
    push ax
    xchg ax, dx                 ; AX = the button's right + 1, CX = the byte - 1
    call bzw_fillh
    pop ax
    cmp ax, [bz_fw]
    jge .out
    jmp bzw_blitsh
.out:
    ret

; bzw_rowpic - a band [bz_wy, + bz_wh) of the content: [0, AX) filled, picture SI
; (its rows from 0) at content x AX, the rest of the width filled.
; bzw_rowpicr - the same with CX = the picture's first row.
bzw_rowpic:
    xor cx, cx
bzw_rowpicr:
    push cx
    push ax
    mov cx, ax
    dec cx
    xor ax, ax
    call bzw_fillh
    pop ax
    pop bx                      ; BX = the picture's row
    push ax
    call bzw_bandptr
    mov cx, [cs:si + 2]
    call bzw_blitsl
    pop ax
    add ax, [cs:si + 2]
    mov cx, [bz_fw]
    dec cx
    jmp bzw_fillh

; bzw_bandptr - BX = a picture's row: [bz_wsrc] = its first byte (in the part)
bzw_bandptr:
    push ax
    push dx
    mov ax, [cs:si + 6]
    mul bx
    add ax, [cs:si]
    mov [bz_wsrc], ax
    pop dx
    pop ax
    ret

; bzw_blitsl - [bz_wh] rows of picture SI from [bz_wsrc] (the part's, CS) at
; content x AX, CX pixels wide, the band's rows [bz_wy]: one BLIT1.
bzw_blitsl:
    push dx                     ; (no wider than the content left of AX)
    mov dx, [bz_fw]
    sub dx, ax
    cmp cx, dx
    jle .w
    mov cx, dx
.w:
    pop dx
    push es
    push bp
    push si
    mov bp, [cs:si + 6]
    push cs
    pop es
    mov si, [bz_wsrc]
    call bzw_blit
    pop si
    pop bp
    pop es
    ret

; bzw_blitsh - the ledge (SI) from content x AX (> its left edge) to its right
; edge: column c = AX - lx shifted to a byte's start, a row at a time into
; bz_font, as many rows a BLIT1 as fit (SPEC.md 137.26.2: nothing twice)
bzw_blitsh:
    push ax
    mov bx, ax
    sub bx, [bz_wlx]            ; BX = c
    mov cx, [cs:si + 2]
    sub cx, bx                  ; CX = the slice's width ...
    mov dx, [bz_fw]
    sub dx, ax
    cmp cx, dx                  ; ...to the content's edge
    jle .sw
    mov cx, dx
.sw:
    mov [bz_wsw], cx
    add cx, 7
    shr cx, 1
    shr cx, 1
    shr cx, 1
    mov [bz_wsb], cx            ; its bytes a row
    mov [bz_wsc], bx
    mov ax, [bz_wy]
    sub ax, [bz_wly]
    mov [bz_wsr], ax            ; the picture's row
    mov ax, [bz_wh]
    mov [bz_wsn], ax            ; rows to go
.chunk:
    mov ax, 512                 ; rows a chunk: 512 / bytes a row
    xor dx, dx
    div word [bz_wsb]
    cmp ax, [bz_wsn]
    jbe .n
    mov ax, [bz_wsn]
.n:
    mov [bz_wh], ax
    push ax
    mov di, bz_font
    mov dx, ax                  ; DX = rows
.row:
    mov bx, [bz_wsr]
    call bzw_bandptr
    push si
    mov si, [bz_wsc]
    mov cl, 3
    shr si, cl
    add si, [bz_wsrc]           ; the byte holding column c
    mov cx, [bz_wsc]
    and cl, 7                   ; the shift
    mov bx, [bz_wsb]
.byte:
    mov ah, [cs:si]
    mov al, [cs:si + 1]         ; (one past the row's last byte: the next row's
    shl ax, cl                  ; first, or the next picture's - its bits fall
    mov [di], ah                ; past the width, where BLIT1 masks them)
    inc si
    inc di
    dec bx
    jnz .byte
    pop si
    inc word [bz_wsr]
    dec dx
    jnz .row
    pop dx
    pop ax                      ; content x
    push ax
    push es
    push bp
    push si
    mov bp, [bz_wsb]
    push ds
    pop es
    mov cx, [bz_wsw]
    mov si, bz_font
    call bzw_blit
    pop si
    pop bp
    pop es
    mov bx, [bz_wh]
    add [bz_wy], bx
    sub [bz_wsn], bx
    jnz .chunk
    pop ax
    ret
; bzw_blit - ES:SI a band, BP its stride, AX content x, CX its width, the
; band's rows [bz_wy, + bz_wh): one BLIT1, a set bit WHITE (1 = lit, the
; 1bpp desktop's own polarity; the pen says the same on a colour one).
; Clobbers AX, BX, DX.
bzw_blit:
    push ax
    mov ax, CWHITE | (CBLACK << 8)
    call OSAPI_GFX_BLIT1_PEN
    pop ax
    add ax, [bz_ox]
    mov bx, [bz_wy]
    add bx, [bz_oy]
    mov dx, [bz_wh]
    call OSAPI_GFX_BLIT1
    ret

; BX = the first content row, DX = the last: white across the whole width
bzw_fillw:
    push ax
    push cx
    xor ax, ax
    mov cx, [bz_fw]
    dec cx
    call bzw_fill
    pop cx
    pop ax
    ret
; AX = x1, CX = x2 (content, inclusive) over the band's rows; nothing when empty
bzw_fillh:
    push bx
    push dx
    mov bx, [bz_wy]
    mov dx, bx
    add dx, [bz_wh]
    dec dx
    call bzw_fill
    pop dx
    pop bx
    ret
bzw_fill:
    cmp cx, ax
    jl .out
    cmp ax, [bz_fw]
    jge .out
    jmp bz_fillrect             ; (clipped to the foot; nothing when DX < BX)
.out:
    ret

; bzw_reason - when Play Game is greyed, or the last launch was refused, ONE
; line of why, centred, at [bz_wy] (a 10-line band: 2 of air and the cell),
; [bz_wy] stepped past it.  Clobbers AX, BX, CX, DX.
bzw_reason:
    push si
    push di
    call bz_adname              ; SI = the adapter's line, or why there is none
    cmp byte [bz_small], 0
    jne .say
    call bz_adapter
    or al, al
    jz .say
    mov si, bz_s_err
    cmp byte [bz_err], 1
    je .say
    mov si, bz_s_err2
    cmp byte [bz_err], 2
    je .say
    mov si, bz_s_err3
    cmp byte [bz_err], 3
    je .say
    mov si, bz_s_err4
    cmp byte [bz_err], 4
    jne .none
.say:
    mov di, bz_lbuf             ; the line, in the package's bss
    call bz_lcat
    mov byte [di], 0
    sub di, bz_lbuf
    mov cl, 3
    shl di, cl                  ; DI = its width in pixels
    mov ax, [bz_fw]
    sub ax, di
    sar ax, 1
    jns .x
    xor ax, ax
.x:
    mov cx, [bz_fw]
    dec cx
    mov [bz_wrr], cx            ; (its right filled to the content's edge)
    call bzw_lbline
.none:
    pop di
    pop si
    ret

; bzw_lbline - the line in bz_lbuf, DI pixels wide, at content x AX, as a
; BZ_LH band at [bz_wy] (2 lines of air and the cell): its left filled, the
; air over its width, the cell by OSAPI_FONT_RUN (ground and glyph in one
; pass), its right filled to column [bz_wrr]; [bz_wy] stepped past it.  Clobbers AX, BX, CX, DX,
; SI.
bzw_lbline:
    mov word [bz_wh], BZ_LH
    push ax
    mov cx, ax
    dec cx
    xor ax, ax
    call bzw_fillh              ; its left
    mov bx, [bz_wy]             ; its 2 lines of air, over its width
    mov dx, bx
    inc dx
    pop ax
    push ax
    mov cx, ax
    add cx, di
    dec cx
    call bzw_fill
    pop ax
    push ax
    mov cx, ax
    add cx, [bz_ox]
    mov dx, [bz_wy]
    add dx, 2
    add dx, [bz_oy]
    mov si, bz_lbuf
    mov ax, CBLACK | (CWHITE << 8)
    call OSAPI_FONT_RUN
    pop ax
    add ax, di                  ; its right, to [bz_wrr]
    mov cx, [bz_wrr]
    call bzw_fillh
    add word [bz_wy], BZ_LH
    ret

; bzw_keys - the player's keys (SPEC.md 137.26.9): BZW_NKEYS lines, left-
; aligned a cell left of the title's left edge, the block centred down the
; space between the title (and a reason) and the Play Game button's top.  A
; line may share rows with the ledge picture when it ends left of it (its
; right filled to the ledge's left, and above the ledge's top the rest; the
; ledge's rows then put down the picture alone up to [bz_wkb]); otherwise the
; block stands above the ledge.  The air above it filled, [bz_wy] and
; [bz_wkb] stepped past it; a band too short draws none.  Clobbers AX, BX,
; CX, DX.
BZW_NKEYS   equ 3
bzw_keyt:
    db 'Roll - Arrow Keys', 0
    db 'Hop / Double Bounce - Space', 0
    db 'Brake - Left Shift', 0
bzw_keys:
    push si
    push di
    mov ax, [bz_wy]
    mov [bz_wkb], ax            ; (none: the ledge's rows its own)
    mov ax, [bz_wby0]           ; the top: centred above the button
    sub ax, [bz_wy]
    sub ax, BZW_NKEYS * BZ_LH
    jl .out
    shr ax, 1
    add ax, [bz_wy]
    mov bx, ax                  ; BX = the block's top
    mov si, bzw_keyt            ; every line meeting the ledge's rows must end
    mov dx, bx                  ; left of the ledge picture, or the block
.ck:                            ; stands above it
    add dx, BZ_LH               ; DX = the line's foot
    call .len                   ; CX = its pixels
    cmp dx, [bz_wly]
    jbe .ck1
    call .x
    add cx, ax
    cmp cx, [bz_wlx]
    jbe .ck1
    mov bx, [bz_wly]
    sub bx, BZW_NKEYS * BZ_LH
    cmp bx, [bz_wy]
    jl .out
    jmp short .go
.ck1:
    cmp si, bzw_keys
    jb .ck
.go:
    push bx                     ; the air above it
    mov dx, bx
    dec dx
    mov bx, [bz_wy]
    call bzw_fillw
    pop bx
    mov [bz_wy], bx
    mov si, bzw_keyt
.line:
    mov ax, [bz_fw]             ; its right: to the content's edge, or to the
    dec ax                      ; ledge's left when it meets the ledge's rows
    mov dx, [bz_wy]
    add dx, BZ_LH
    cmp dx, [bz_wly]
    jbe .r
    mov ax, [bz_wly]            ; (its rows above the ledge's top: the rest of
    cmp ax, [bz_wy]             ; the width filled here)
    jle .r1
    push ax
    mov ax, [bz_wlx]
    mov cx, [bz_fw]
    dec cx
    mov bx, [bz_wy]
    pop dx
    dec dx
    call bzw_fill
.r1:
    mov ax, [bz_wlx]
    dec ax
.r:
    mov [bz_wrr], ax
    mov di, bz_lbuf
    call bz_lcat                ; SI past the line's NUL
    mov byte [di], 0
    sub di, bz_lbuf
    mov cl, 3
    shl di, cl                  ; DI = its width in pixels
    call .x
    push si
    call bzw_lbline
    pop si
    cmp si, bzw_keys
    jb .line
    mov ax, [bz_wy]
    mov [bz_wkb], ax
.out:
    pop di
    pop si
    ret
; AX = the block's left: a cell left of the title's, at least 0
.x:
    mov ax, [bz_wtx]
    sub ax, 8
    jns .xr
    xor ax, ax
.xr:
    ret
; SI a line: CX = its width in pixels, SI past its NUL
.len:
    xor cx, cx
.l:
    cmp byte [cs:si], 0
    je .le
    inc si
    add cx, 8
    jmp short .l
.le:
    inc si
    ret
