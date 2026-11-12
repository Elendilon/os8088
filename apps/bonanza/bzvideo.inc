; bzvideo.inc - BONANZA's bracket, mode, retrace wait, ring writers and boxes
; (SPEC.md 128.2, 128.4).  Shapes from Excitebike's CGA/Hercules engine
; (apps/excitebike/cga.inc, herc.inc, SPEC.md 102), made two-dimensional.
;
; THE RING (SPEC.md 128.2).  On both cards the 6845's start address S counts
; WORDS and the card decodes 12 bits of it, so each bank is a ring of 4,096
; words.  The world is stored SHEARED: the byte of world line L, world byte
; column b is
;     CGA       (L&1)*2000h + (80*(L>>1) + b) mod 8192
;     Hercules  (L&3)*2000h + (90*(L>>2) + b) mod 8192
; i.e. world card row R = L >> lsh holds its word column c at ring word
; (W*R + c) mod 4096, whatever the scroll.  Scrolling is S = (W*R0 + c0) mod
; 4096 alone.  Generic over the two cards through the bz_W/bz_H/bz_rb/bz_rl/
; bz_lsh/bz_bend variables bz_vinit sets; the column writer has one body per
; card (the bank count is its unrolled inner step).
;
; Costs (predicted, 8088 at 4.77 MHz, a CGA VRAM word ~86 clocks): a CGA row
; is 80 words, ~10k clocks; a column 200 words, ~24k; a Hercules row 180
; words, ~25k, a column 200 words, ~26k.  Wave 0 is a spike: these are the
; first bodies, priced by the bonanzaperf row and optimised after.

BZ_HR6      equ 50              ; Hercules CRTC R6: 50 rows of 4 lines = the 200-line
BZ_HR7      equ 68              ; field (SPEC.md 102.7.1), R7 its vertical sync
BZ_LINES    equ 200             ; window lines on both cards
BZ_RELW     equ 18              ; sub-ticks the launching key gets to release
BZ_MLIMC    equ 29870           ; 1.5 refreshes in PIT counts: a CGA frame (59.92 Hz,
BZ_MLIMH    equ 35795           ; 19,913) and a Hercules one (taken as 50 Hz,
                                ; 23,864; MartyPC measures 50.8 Hz, so this is
                                ; ~1.52 of its refreshes) - a longer period
                                ; missed a retrace (bz_miss)

; -----------------------------------------------------------------------------
; bz_fullscreen - the bracket proc.  DS = CS = our segment, ES = KERNEL_SEG,
; SI = our window.  bz_launch fetched the adapter's two parts on the desktop
; ([bz_cseg], [bz_bseg]) and set [bz_herc].
; -----------------------------------------------------------------------------
bz_fullscreen:
    cld
    OS88_ALTENTER_SEED
    ; Let the key that got us here (Enter, F or B) release before the mode set
    ; can mask its break.  The wait is the bracket's, never the scheduler's,
    ; and BOUNDED: OSAPI_KEY_DOWN is advice (a break lost in a long
    ; interrupts-off stretch leaves a key reading down for good), so after
    ; BZ_RELW sub-ticks (~0.33 s, ample for a real release) the mode is set
    ; anyway rather than the desktop staying frozen with nothing on the glass.
    mov cx, BZ_RELW
.release:
    mov al, KSC_ENTER
    call OSAPI_KEY_DOWN
    jc .wait
    mov al, BZ_KSC_F
    call OSAPI_KEY_DOWN
    jc .wait
    mov al, BZ_KSC_B
    call OSAPI_KEY_DOWN
    jnc .mode
.wait:
    mov al, FSXW_FRAME
    call OSAPI_FSX_WAIT
    loop .release
.mode:
    call bz_adapter             ; the display must still be the one the desktop
    dec al                      ; fetched the parts for
    cmp al, [bz_herc]
    jne .moved
    mov al, FSXM_CGA320
    cmp byte [bz_herc], 0
    je .set
    mov al, FSXM_HERC
.set:
    push ds
    pop es
    mov di, bz_fsi
    call OSAPI_FSX_MODE
    jc .refused
    mov byte [bz_fs], 1
    call bz_vinit
    call bz_play                ; the frame loop, until a key or the benchmark ends
    xor ax, ax                  ; the start address home on the way out (the
    call bz_flip                ; kernel's restore re-sets the mode anyway)
    mov byte [bz_fs], 0
    ret
.moved:
    mov byte [bz_err], 2
    ret
.refused:
    mov byte [bz_err], 1
    ret

; -----------------------------------------------------------------------------
; bz_vinit - the card's geometry, after OSAPI_FSX_MODE.  The Hercules is put on
; Excitebike's 200-line field (R6 = 50, R7 = 68).  Preserves nothing.
; -----------------------------------------------------------------------------
bz_vinit:
    mov ax, [bz_fsi + FSI_SEG]
    mov [bz_vseg], ax
    cmp byte [bz_herc], 0
    jne .herc
    mov word [bz_W], 40
    mov word [bz_H], 100
    mov word [bz_rb], 80
    mov word [bz_rl], 2
    mov byte [bz_lsh], 1
    mov word [bz_bend], 4000h
    mov word [bz_crtc], 3d4h
    mov word [bz_cmax], BZ_COLS - 40
    mov word [bz_rmax], BZ_BROWS * 8 / 2 - 100
    mov word [bz_vrport], 3dah
    mov word [bz_vrbits], 0008h ; 3DAh bit 3 HIGH: in the retrace
    mov word [bz_vrlim], 2      ; ...given up after two sub-ticks
    mov word [bz_mlim], BZ_MLIMC
    ret
.herc:
    mov word [bz_W], 45
    mov word [bz_H], 50
    mov word [bz_rb], 90
    mov word [bz_rl], 4
    mov byte [bz_lsh], 2
    mov word [bz_bend], 8000h
    mov word [bz_crtc], 3b4h
    mov word [bz_cmax], BZ_COLS - 45
    mov word [bz_rmax], BZ_BROWS * 8 / 4 - 50
    mov word [bz_vrport], 3bah
    mov word [bz_vrbits], 8080h ; 3BAh bit 7 LOW: in the retrace
    mov word [bz_vrlim], 3      ; ...three sub-ticks (a 50 Hz field)
    mov word [bz_mlim], BZ_MLIMH
    mov dx, 3b4h
    mov ax, BZ_HR6 * 256 + 6
    out dx, ax
    mov ax, BZ_HR7 * 256 + 7
    out dx, ax
    ret

; -----------------------------------------------------------------------------
; bz_flip - AX = a start address (words, < 4096) to R12 (high), R13 (low).
; The 6845 latches it at the next retrace.  Preserves all but the flags.
; -----------------------------------------------------------------------------
bz_flip:
    push ax
    push cx
    push dx
    mov dx, [bz_crtc]
    mov cx, ax
    mov al, 0ch
    mov ah, ch
    out dx, ax
    mov al, 0dh
    mov ah, cl
    out dx, ax
    pop dx
    pop cx
    pop ax
    ret

; -----------------------------------------------------------------------------
; bz_vr - the retrace wait (SPEC.md 128.4): the CGA's 3DAh bit 3 high, the
; Hercules's 3BAh bit 7 low - the LEVEL, as Excitebike's xc_vr - bounded by
; two sub-ticks (three on the Hercules), the clock sampled between reads.  Its
; time is IDLE (the bz_tv part).  A timeout counts in [bz_tos] and the frame
; goes on.  Preserves all but the flags.
; -----------------------------------------------------------------------------
bz_vr:
    push ax
    push bx
    push cx
    push dx
    call bz_clk_sample
    mov cx, [bz_subs]
    mov dx, [bz_vrport]
    mov bx, [bz_vrbits]
.spin:
    in al, dx
    xor al, bh
    test al, bl
    jnz .done
    call bz_clk_sample
    mov ax, [bz_subs]
    sub ax, cx
    cmp ax, [bz_vrlim]
    jb .spin
    inc word [bz_tos]           ; no retrace at all: go on regardless
.done:
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; bz_row - THE ROW WRITER (SPEC.md 128.2 rules 1 and the full write): world
; card row AX, world word columns BX .. BX+CX-1, every line of the row (2 on
; the CGA, 4 on the Hercules), each word drawn from the course: the word of
; (map[L>>3][c] + 2*(L&7)).  A line is contiguous on the card, so the only
; split is where it crosses the 8KB ring end.  DS = ours on entry.  Preserves
; every register.  [bz_nrow] counts the calls (a harness also counts entries
; at this global label).
;
; Stack frame (SS, BP): [bp+0] the map pointer of the row's first word,
; [bp+2] the line's ring offset in bank 0 (DI0), [bp+4] the end bank,
; [bp+6] the current bank.
; -----------------------------------------------------------------------------
bz_row:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    push es
    push ds
    inc word [bz_nrow]
    mov es, [bz_vseg]
    push cx                     ; the word count
    push ax
    mul word [bz_rb]
    mov di, bx
    shl di, 1
    add di, ax
    and di, 1fffh               ; DI0 = (rb*R + 2c) mod 8192
    pop ax
    mov cl, [bz_lsh]
    shl ax, cl                  ; AX = L0, the row's first world line
    mov dx, ax
    and dx, 7
    shl dx, 1
    add dx, BZ_CRS_BLKOFF       ; DX = the line word's offset in a block
    and ax, 0fff8h
    mov cl, 4
    shl ax, cl                  ; (L0 >> 3) * 128: the block row's map
    add ax, BZ_CRS_MAPOFF
    add ax, bx
    add ax, bx                  ; AX = the map pointer of the first word
    mov si, [bz_bend]
    pop cx
    sub sp, 8
    mov bp, sp
    mov [bp + 0], ax
    mov [bp + 2], di
    mov [bp + 4], si
    mov word [bp + 6], 0
    mov ax, 2000h               ; the words before the ring's end
    sub ax, di
    shr ax, 1
    cmp ax, cx
    jbe .n1
    mov ax, cx
.n1:
    sub cx, ax
    mov ah, cl                  ; AL = n1 (before the wrap), AH = n2 (after)
    mov ds, [bz_cseg]           ; DS = the course from here
.line:
    mov bx, [bp + 0]
    mov di, [bp + 2]
    add di, [bp + 6]
    mov cl, al
    xor ch, ch
.w1:
    mov si, [bx]
    add si, dx
    movsw
    inc bx
    inc bx
    loop .w1
    mov cl, ah
    jcxz .nl
    mov di, [bp + 6]            ; ...and on from the ring's start
.w2:
    mov si, [bx]
    add si, dx
    movsw
    inc bx
    inc bx
    loop .w2
.nl:
    inc dx                      ; the next line of the same blocks
    inc dx
    mov cx, [bp + 6]
    add cx, 2000h
    mov [bp + 6], cx
    cmp cx, [bp + 4]
    jb .line
    add sp, 8
    pop ds
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
; bz_col - THE COLUMN WRITER (SPEC.md 128.2 rule 3): world word column AX,
; CX rows (at least 1) of the NEW window from its row BX (0 = the top: rows
; [bz_R0n]+BX ..), TOP ROW FIRST AND IN RASTER ORDER - line by line, so each
; bank's word goes out before the beam reaches it.  Written after the start
; address, from the retrace; a frame may write one column in two calls, split
; round the boxes (bzgame.inc bz_csplit).  A row's lines are one block's (2 or
; 4 of its 8), so the source walks a block's line words and steps to the next
; block row's map entry every 4 (CGA) or 2 (Hercules) rows.  DS = ours on
; entry.  Preserves every register.  [bz_ncol] counts the COLUMNS (the caller).
; -----------------------------------------------------------------------------
bz_col:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    push ds
    mov es, [bz_vseg]
    push cx                     ; the rows
    add bx, [bz_R0n]            ; BX = R, the first world card row
    push bx
    xchg ax, bx                 ; BX = c, AX = R
    mul word [bz_rb]
    mov di, bx
    shl di, 1
    add di, ax
    and di, 1fffh               ; DI = (rb*R + 2c) mod 8192, bank 0
    pop ax                      ; AX = R
    mov cl, [bz_lsh]
    shl ax, cl                  ; AX = L0
    mov dx, ax
    and dx, 7                   ; DL = the line in its block
    shl bx, 1
    and ax, 0fff8h
    mov cl, 4
    shl ax, cl
    add bx, ax
    add bx, BZ_CRS_MAPOFF       ; BX = the map entry of the first block
    pop cx                      ; CX = the rows
    cmp byte [bz_herc], 0
    mov ds, [bz_cseg]           ; (MOV keeps the flags)
    jne .herc
    mov si, [bx]
    add si, BZ_CRS_BLKOFF
    add si, dx
    add si, dx                  ; SI = the first line's word
    neg dl
    add dl, 8                   ; DL = the lines left in this block
.rc:
    lodsw
    mov [es:di], ax
    lodsw
    mov [es:di + 2000h], ax
    add di, 80
    and di, 1fffh
    sub dl, 2
    jnz .nc
    add bx, BZ_CRS_ROWB
    mov si, [bx]
    add si, BZ_CRS_BLKOFF
    mov dl, 8
.nc:
    loop .rc
    jmp .out
.herc:
    mov si, [bx]
    add si, BZ_CRS_BLKOFF
    add si, dx
    add si, dx
    neg dl
    add dl, 8
.rh:
    lodsw
    mov [es:di], ax
    lodsw
    mov [es:di + 2000h], ax
    lodsw
    mov [es:di + 4000h], ax
    lodsw
    mov [es:di + 6000h], ax
    add di, 90
    and di, 1fffh
    sub dl, 4
    jnz .nh
    add bx, BZ_CRS_ROWB
    mov si, [bx]
    add si, BZ_CRS_BLKOFF
    mov dl, 8
.nh:
    loop .rh
.out:
    pop ds
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; THE BOXES (SPEC.md 128.4).  A box is a rectangle of the world in WORDS x
; LINES, composed in RAM from the course and the ball (mask AND, frame OR) and
; then written to the card a line at a time.  Descriptor, BZ_BOXD bytes:
; +0 x0 (world word column), +2 y0 (world line), +4 w (words), +6 h (lines),
; +8 the buffer.  At most two boxes a frame (bzgame.inc bz_mkboxes): the union
; of the old and new footprints when it fits BZ_BOXW x BZ_BOXH, else each.
; -----------------------------------------------------------------------------
BZ_BOXW     equ 4               ; words (8 bytes)
BZ_BOXH     equ 24              ; lines
BZ_BOXB     equ BZ_BOXW * 2 * BZ_BOXH
BZ_BOXD     equ 10

; bz_boxc - compose box SI (a descriptor): fill from the course, then the ball
; at [bz_px], [bz_py] with frame [bz_frm].  DS = ours.  Preserves all.
bz_boxc:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    push es
    push ds
    pop es                      ; ES = ours: the buffer
    ; --- the course: line by line, word by word ---
    mov di, [si + 8]
    mov ax, [si + 2]            ; AX = the line L
    mov bp, [si + 6]            ; BP = lines left
    mov cx, [si + 4]
    mov [bz_bw], cx
    mov bx, [si]
    shl bx, 1
    mov [bz_bx2], bx            ; 2 * x0
    push ds
.fline:
    pop ds                      ; (DS = ours for the bss reads)
    push ds
    mov dx, ax
    and dx, 7
    shl dx, 1
    add dx, BZ_CRS_BLKOFF       ; DX = the line's word in each block
    mov bx, ax
    and bx, 0fff8h
    shl bx, 1
    shl bx, 1
    shl bx, 1
    shl bx, 1
    add bx, BZ_CRS_MAPOFF
    add bx, [bz_bx2]            ; BX = the map entry of x0
    mov cx, [bz_bw]
    mov ds, [bz_cseg]
.fw:
    mov si, [bx]
    add si, dx
    movsw
    inc bx
    inc bx
    loop .fw
    inc ax
    dec bp
    jnz .fline
    pop ds
    pop es
    pop bp
    pop di
    pop si                      ; SI = the descriptor again
    push si
    push di
    push bp
    push es
    push ds                     ; (the ball's DS is undone at .noball)
    push ds
    pop es
    ; --- the ball, clipped to the box ---
    ; rows i in [imin, imax): py + i inside [y0, y0+h)
    mov ax, [si + 2]
    sub ax, [bz_py]             ; y0 - py
    jge .imin
    xor ax, ax
.imin:
    mov [bz_imin], ax
    mov ax, [si + 2]
    add ax, [si + 6]
    sub ax, [bz_py]             ; y0 + h - py
    cmp ax, BZ_BAL_ROWS
    jle .imax
    mov ax, BZ_BAL_ROWS
.imax:
    sub ax, [bz_imin]
    jle .noball
    mov bp, ax                  ; BP = the rows
    ; bytes k in [kmin, kmax): px/4 + k inside [2x0, 2x0 + 2w)
    mov cx, [bz_px]
    shr cx, 1
    shr cx, 1                   ; CX = the ball's first world byte
    mov ax, [si]
    shl ax, 1
    sub ax, cx                  ; 2x0 - bc
    jge .kmin
    xor ax, ax
.kmin:
    mov [bz_kmin], ax
    mov ax, [si]
    add ax, [si + 4]
    shl ax, 1
    sub ax, cx                  ; 2x0 + 2w - bc
    cmp ax, BZ_BAL_RB
    jle .kmax
    mov ax, BZ_BAL_RB
.kmax:
    sub ax, [bz_kmin]
    jle .noball
    push ax                     ; the bytes a row
    ; the destination: buf + (py + imin - y0) * 2w + (bc + kmin - 2x0)
    mov ax, [bz_py]
    add ax, [bz_imin]
    sub ax, [si + 2]
    mov dx, [si + 4]
    shl dx, 1                   ; DX = 2w, the buffer's stride
    push dx
    mul dx
    mov di, ax
    add di, [si + 8]
    add di, cx
    add di, [bz_kmin]
    mov ax, [si]
    shl ax, 1
    sub di, ax
    ; the masks: 16 + s*80 + imin*5 + kmin; the frames: 336 + s*5120 + f*80 + ...
    mov ax, [bz_imin]
    mov dx, BZ_BAL_RB
    mul dx
    add ax, [bz_kmin]
    mov cx, ax                  ; CX = imin*5 + kmin
    mov ax, [bz_px]
    and ax, 3                   ; s
    push ax
    mov dx, BZ_BAL_MASKSH
    mul dx
    add ax, BZ_BAL_MASKOFF
    add ax, cx
    mov si, ax                  ; SI = the first mask byte
    pop ax
    mov dx, BZ_BAL_FRMSH
    mul dx
    add ax, BZ_BAL_FRMOFF
    add ax, cx
    mov bx, ax
    mov ax, [bz_frm]
    mov dx, BZ_BAL_FRMB
    mul dx
    add bx, ax                  ; BX = the first frame byte
    pop dx                      ; DX = 2w
    pop ax                      ; AX = the bytes a row
    mov ah, al
    mov ds, [bz_bseg]           ; DS = the ball from here
.brow:
    push si
    push bx
    push di
    mov cl, ah
    xor ch, ch
.bb:
    mov al, [es:di]
    and al, [si]                ; a set mask bit keeps the course
    or al, [bx]                 ; ...and the frame is pre-ANDed (SPEC.md 128.3)
    mov [es:di], al
    inc si
    inc bx
    inc di
    loop .bb
    pop di
    pop bx
    pop si
    add si, BZ_BAL_RB
    add bx, BZ_BAL_RB
    add di, dx
    dec bp
    jnz .brow
.noball:
    pop ds
    pop es
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; bz_boxw - box SI (a descriptor) to the card, a line at a time, each line
; split where it crosses the ring's 8KB end.  DS = ours.  Preserves all.
bz_boxw:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    push es
    mov es, [bz_vseg]
    mov ax, [si + 4]
    mov [bz_bw], ax
    mov bp, [si + 6]            ; BP = lines left
    mov ax, [si + 2]            ; the first line L
    mov cl, [bz_lsh]
    mov bx, ax
    shr ax, cl                  ; R = L >> lsh
    mov cx, [bz_rl]
    dec cx
    and bx, cx                  ; L & (rl-1)
    mov cl, 13
    shl bx, cl                  ; BX = the bank
    mul word [bz_rb]
    mov dx, [si]
    shl dx, 1
    add dx, ax
    and dx, 1fffh               ; DX = the line's offset in its bank
    mov si, [si + 8]            ; SI = the buffer
.line:
    mov di, dx
    add di, bx
    mov cx, [bz_bw]
    mov ax, cx
    shl ax, 1
    add ax, dx
    cmp ax, 2000h
    ja .split
    rep movsw
    jmp .next
.split:
    mov ax, 2000h
    sub ax, dx
    shr ax, 1                   ; the words before the ring's end
    sub cx, ax
    xchg ax, cx
    rep movsw
    mov cx, ax
    mov di, bx
    rep movsw
.next:
    add bx, 2000h
    cmp bx, [bz_bend]
    jb .same
    xor bx, bx
    add dx, [bz_rb]
    and dx, 1fffh
.same:
    dec bp
    jnz .line
    pop es
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret
