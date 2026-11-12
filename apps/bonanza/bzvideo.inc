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
; words, ~25k, a column 200 words, ~26k.  Wave 0's first bodies were priced
; by the bonanzaperf row and wave 0b's optimisation round (SPEC.md 128.9 items
; 1-6) rewrote them; MartyPC then measured a CGA row at ~8.5k (10.4k in wave
; 0) and a column frame at ~24.8k (25.7k): both are bound by the card's own
; write cost now, not by the instructions round it.

BZ_HR6      equ 50              ; Hercules CRTC R6: 50 rows of 4 lines = the 200-line
BZ_HR7      equ 68              ; field (SPEC.md 102.7.1), R7 its vertical sync
BZ_LINES    equ 200             ; window lines on both cards
BZ_RELW     equ 18              ; sub-ticks the launching key gets to release
BZ_MLIMC    equ 29870           ; 1.5 refreshes in PIT counts: a CGA frame (59.92 Hz,
BZ_MLIMH    equ 35795           ; 19,913) and a Hercules one (taken as 50 Hz,
                                ; 23,864; MartyPC measures 50.8 Hz, so this is
                                ; ~1.52 of its refreshes) - a longer period
                                ; missed a retrace (bz_miss)
BZ_LBLC     equ 22 * 76         ; PIT counts from the vertical sync's END to the
BZ_LBLH     equ 82 * 63         ; first window line: the CGA's 6845 syncs 16 lines
                                ; from line 224 of 262 (R4 127, R5 6, R7 112), a
                                ; line 304 clocks = 76 counts; the Hercules field
                                ; from line 272 of 370 (R4 91, R5 2, R7 68), a
                                ; line ~254 clocks, taken as 63 counts (low, so
                                ; the budget errs short).  bz_latechk's beam.

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
    mov word [bz_lblank], BZ_LBLC
    mov word [bz_gfx], BZ_GFXC  ; GLIDE's "fast" at this card's refresh
    mov word [bz_gfy], BZ_GFYC
    jmp short .wtab
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
    mov word [bz_lblank], BZ_LBLH
    mov word [bz_gfx], BZ_GFXH
    mov word [bz_gfy], BZ_GFYH
    mov dx, 3b4h
    mov ax, BZ_HR6 * 256 + 6
    out dx, ax
    mov ax, BZ_HR7 * 256 + 7
    out dx, ax
.wtab:                          ; W * dr for dr = -2 .. 2 (bz_tf's S)
    mov ax, [bz_W]
    mov [bz_wtab + 6], ax
    neg ax
    mov [bz_wtab + 2], ax
    shl ax, 1
    mov [bz_wtab], ax
    neg ax
    mov [bz_wtab + 8], ax
    mov word [bz_wtab + 4], 0
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
; goes on.  The last clock sample is kept ([bz_vsubs], [bz_vpit]), and
; [bz_vedge] says whether the wait saw the sync RISE - a read outside it first,
; so the sample is within one turn of the loop (~1 line) of the sync's START -
; or found it already high, anywhere in its 16 lines (bz_latechk).  Preserves
; all but the flags.
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
    mov byte [bz_vedge], 0
.spin:
    in al, dx
    xor al, bh
    test al, bl
    jnz .done
    mov byte [bz_vedge], 1      ; outside the sync: the next read that finds
    call bz_clk_sample          ; it finds its start
    mov ax, [bz_subs]
    sub ax, cx
    cmp ax, [bz_vrlim]
    jb .spin
    inc word [bz_tos]           ; no retrace at all: go on regardless
.done:
    mov ax, [bz_subs]           ; the last sample before the retrace was seen:
    mov [bz_vsubs], ax          ; bz_latechk reckons the beam from it
    mov ax, [bz_pitl]
    mov [bz_vpit], ax
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; bz_rbR - AX = a world card row R -> AX = rb * R (mod 64K; every caller masks
; it to the 8KB ring): the CGA's 80 R = 64 R + 16 R, the Hercules' 90 R =
; 64 R + 16 R + 8 R + 2 R - shifts and adds where wave 0 had a MUL (SPEC.md
; 128.9 item 4).  NO FASTER than that MUL: with the call, the push/pop and
; the card test at the 8088's fetch floor it is ~170 clocks on the CGA and
; ~190 on the Hercules against ~150 for `mul word [bz_rb]` and its operand
; (wave 0b's review); it stays because it leaves DX alone.  And since rb = 2W,
; (rb * R) / 2 is W * R, the start address's product (a full write's S).
; Preserves all but AX and the flags.
; -----------------------------------------------------------------------------
bz_rbR:
    push dx
    shl ax, 1                   ; 2R
    cmp byte [bz_herc], 0
    jne .herc
    shl ax, 1
    shl ax, 1
    shl ax, 1                   ; 16R
    mov dx, ax
    shl ax, 1
    shl ax, 1                   ; 64R
    add ax, dx                  ; 80R
    pop dx
    ret
.herc:
    mov dx, ax                  ; 2R
    shl ax, 1
    shl ax, 1                   ; 8R
    add dx, ax                  ; 10R
    shl ax, 1                   ; 16R
    add dx, ax                  ; 26R
    shl ax, 1
    shl ax, 1                   ; 64R
    add ax, dx                  ; 90R
    pop dx
    ret

; -----------------------------------------------------------------------------
; bz_row - THE ROW WRITER (SPEC.md 128.2 rules 1 and the full write): world
; card row AX, world word columns BX .. BX+CX-1 (CX at least 1), every line of
; the row (2 on the CGA, 4 on the Hercules), each word drawn from the course:
; the word of (map[L>>3][c] + 2*(L&7)).  DS = ours on entry.  Preserves every
; register.  [bz_nrow] counts the calls (a harness also counts entries at this
; global label).
;
; WORD COLUMNS OUTERMOST (SPEC.md 128.9 item 3): a row's lines all come from
; the same block row, so each word column's map entry is read ONCE and its 2
; (4) line words go to the 2 (4) banks at the same offset - wave 0 read the map
; once a LINE, twice (four times) a word.  A row is contiguous in every bank
; at one offset, so the only split is where it crosses the 8KB ring end, and
; it is at the same word in every bank.  The loop runs two words a turn.
; A row is written into the slack (rule 1) or by the full write, so its order
; inside the row is free.
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
    mov si, ax                  ; SI = R
    call bz_rbR
    mov di, bx
    shl di, 1
    add di, ax
    and di, 1fffh               ; DI = (rb*R + 2c) mod 8192, bank 0
    mov ax, si
    push cx
    mov cl, [bz_lsh]
    shl ax, cl                  ; AX = L0, the row's first world line
    mov dx, ax
    and dx, 7
    shl dx, 1
    add dx, BZ_CRS_BLKOFF       ; DX = the first line's word in a block
    and ax, 0fff8h
    mov cl, 4
    shl ax, cl                  ; (L0 >> 3) * 128: the block row's map
    add ax, BZ_CRS_MAPOFF
    shl bx, 1
    add bx, ax                  ; BX = the map entry of the first word
    pop cx
    mov ax, 2000h               ; the words before the ring's end
    sub ax, di
    shr ax, 1
    cmp ax, cx
    jbe .n1
    mov ax, cx
.n1:
    sub cx, ax
    mov bp, cx                  ; BP = the words after the wrap
    mov cx, ax                  ; CX = the words before it (at least 1)
    cmp byte [bz_herc], 0
    mov ds, [bz_cseg]           ; DS = the course from here (MOV keeps the flags)
    jne .herc
.cga:
    shr cx, 1                   ; two words a turn; an odd count enters at
    jnc .c0                     ; the pair's second half
    inc cx
    jmp short .c1
.c0:
    mov si, [bx]
    add si, dx
    lodsw
    stosw
    lodsw
    mov [es:di + 1ffeh], ax
    inc bx
    inc bx
.c1:
    mov si, [bx]
    add si, dx
    lodsw
    stosw
    lodsw
    mov [es:di + 1ffeh], ax
    inc bx
    inc bx
    loop .c0
    mov cx, bp                  ; ...and on from the ring's start
    jcxz .out
    xor bp, bp
    xor di, di
    jmp short .cga
.herc:
    shr cx, 1
    jnc .h0
    inc cx
    jmp short .h1
.h0:
    mov si, [bx]
    add si, dx
    lodsw
    stosw
    lodsw
    mov [es:di + 1ffeh], ax
    lodsw
    mov [es:di + 3ffeh], ax
    lodsw
    mov [es:di + 5ffeh], ax
    inc bx
    inc bx
.h1:
    mov si, [bx]
    add si, dx
    lodsw
    stosw
    lodsw
    mov [es:di + 1ffeh], ax
    lodsw
    mov [es:di + 3ffeh], ax
    lodsw
    mov [es:di + 5ffeh], ax
    inc bx
    inc bx
    loop .h0
    mov cx, bp
    jcxz .out
    xor bp, bp
    xor di, di
    jmp short .herc
.out:
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
; address, from the retrace; a frame may write one column in two or three
; calls, split round the boxes (bzgame.inc bz_csplit).  DS = ours on entry.
; Preserves every register.  [bz_ncol] counts the COLUMNS (the caller).
;
; SPEC.md 128.9 item 2: the ring's WRAP ROW is found once (a column of H rows
; spans less than the ring, so its offset wraps at most once), and a block's
; rows run UNROLLED - 4 a block on the CGA (2 lines each), 2 on the Hercules
; (4 lines each) - so a row costs its words and an ADD, with no mask, count
; or branch of its own.  A run is the rows left in the block, cut at the wrap
; row and at the rows asked for; it enters its unrolled block at the run's
; length.
; -----------------------------------------------------------------------------
%macro BZ_CROW 0                ; a CGA row: bank 0, bank 1, the next row
    lodsw
    stosw
    lodsw
    mov [es:di + 1ffeh], ax
    add di, byte 80 - 2
%endmacro
%macro BZ_HROW 0                ; a Hercules row: banks 0-3, the next row
    lodsw
    stosw
    lodsw
    mov [es:di + 1ffeh], ax
    lodsw
    mov [es:di + 3ffeh], ax
    lodsw
    mov [es:di + 5ffeh], ax
    add di, byte 90 - 2
%endmacro
bz_col:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    push es
    push ds
    mov es, [bz_vseg]
    push cx                     ; the rows
    add bx, [bz_R0n]            ; BX = R, the first world card row
    mov si, ax
    shl si, 1                   ; SI = 2c
    mov ax, bx
    call bz_rbR
    add ax, si
    and ax, 1fffh
    mov di, ax                  ; DI = (rb*R + 2c) mod 8192, bank 0
    mov ax, 2000h - 1           ; the rows that start before the ring's end:
    sub ax, di                  ; ceil((8192 - DI) / rb), one DIV a column
    add ax, [bz_rb]
    div byte [bz_rb]            ; AL = the rows (at most 103), rb < 256
    xor ah, ah
    mov bp, ax                  ; BP = the rows before the wrap (at least 1)
    mov ax, bx
    mov cl, [bz_lsh]
    shl ax, cl                  ; AX = L0
    mov dx, ax
    and dx, 7                   ; the line in its block
    and ax, 0fff8h
    mov cl, 4
    shl ax, cl
    add ax, BZ_CRS_MAPOFF
    add si, ax
    mov bx, si                  ; BX = the map entry of the first block
    pop cx                      ; CX = the rows
    mov ax, cx                  ; the first RUN: the rows before the wrap row
    cmp ax, bp
    jbe .w1
    mov ax, bp
.w1:
    sub cx, ax
    mov bp, cx                  ; BP = the rows after it (0: no wrap)
    mov cx, ax                  ; CX = the run (at least 1, at most 103)
    cmp byte [bz_herc], 0
    mov ds, [bz_cseg]           ; (MOV keeps the flags)
    jne .herc
    mov si, [bx]
    add si, BZ_CRS_BLKOFF
    add si, dx
    add si, dx                  ; SI = the first line's word
    shr dl, 1
    neg dl
    add dl, 4                   ; DL = the rows left in this block (1..4)
    cmp dl, 4
    jne .cseg
    sub bx, BZ_CRS_ROWB         ; at the block's top: the block loop loads it
    mov dl, 0
.cseg:                          ; a run of CX rows, DL left in the block
    or dl, dl
    jz .cwhole
    mov al, dl                  ; the block's rest, cut at the run's end
    cmp al, cl
    jbe .cp
    mov al, cl
.cp:
    sub cl, al
    sub dl, al
    call .cch
    jcxz .cnext                 ; (then DL may be rows the block still has)
.cwhole:                        ; DL = 0: whole blocks, then a tail
    mov dl, cl
    and dl, 3                   ; DL = the tail's rows
    shr cx, 1
    shr cx, 1                   ; CX = the whole blocks
    jcxz .ctail
.cblk:
    add bx, BZ_CRS_ROWB         ; the next block row
    mov si, [bx]
    add si, BZ_CRS_BLKOFF
    BZ_CROW
    BZ_CROW
    BZ_CROW
    BZ_CROW
    loop .cblk
.ctail:
    mov al, dl
    or al, al
    jz .cnext
    add bx, BZ_CRS_ROWB
    mov si, [bx]
    add si, BZ_CRS_BLKOFF
    neg dl
    add dl, 4                   ; the rows the block has left after the tail
    call .cch
.cnext:
    or bp, bp                   ; the run after the wrap row: from the ring's
    jz .out                     ; start
    mov cx, bp
    xor bp, bp
    sub di, 2000h
    jmp .cseg
.herc:
    mov si, [bx]
    add si, BZ_CRS_BLKOFF
    add si, dx
    add si, dx
    cmp dl, 4                   ; the first line in the block's second row:
    jae .hseg1                  ; one row left in it
    sub bx, BZ_CRS_ROWB         ; at the block's top: the block loop loads it
.hseg:
    mov dl, cl                  ; whole blocks (two rows), then a tail
    and dl, 1
    shr cx, 1
    jcxz .htail
.hblk:
    add bx, BZ_CRS_ROWB
    mov si, [bx]
    add si, BZ_CRS_BLKOFF
    BZ_HROW
    BZ_HROW
    loop .hblk
.htail:
    or dl, dl                   ; DL = 1: the run ends inside a block
    jz .hnext
    add bx, BZ_CRS_ROWB
    mov si, [bx]
    add si, BZ_CRS_BLKOFF
    call .hrow
.hnext:
    or bp, bp                   ; the run after the wrap row
    jz .out
    mov cx, bp
    xor bp, bp
    sub di, 2000h
    or dl, dl
    jz .hseg
.hseg1:                         ; the block's second row first
    call .hrow
    dec cx
    jnz .hseg
    mov dl, 0                   ; (its block is done)
    jmp short .hnext
.out:
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
.cch:                           ; AL rows (1..3) of the CGA block at SI
    cmp al, 2
    jb .c1
    je .c2
    BZ_CROW
.c2:
    BZ_CROW
.c1:
    BZ_CROW
    ret
.hrow:                          ; one Hercules row
    BZ_HROW
    ret

; -----------------------------------------------------------------------------
; THE BOXES (SPEC.md 128.4).  A box is a rectangle of the world in WORDS x
; LINES, composed in RAM from the course and the ball (mask AND, frame OR) and
; then written to the card a line at a time.  Descriptor, BZ_BOXD bytes:
; +0 x0 (world word column), +2 y0 (world line), +4 w (words), +6 h (lines),
; +8 the buffer.  At most two boxes a frame (bzgame.inc bz_mkboxes): the union
; of the old and new footprints when it fits BZ_BOXW x BZ_BOXH, else each.
; A buffer's lines are BZ_BOXW words apart whatever the box's w (SPEC.md 128.9
; item 1: a fixed stride is what lets the fill and the ball step by a
; constant).
; -----------------------------------------------------------------------------
BZ_BOXW     equ 4               ; words (8 bytes)
BZ_BOXH     equ 24              ; lines
BZ_BOXB     equ BZ_BOXW * 2 * BZ_BOXH
BZ_BOXD     equ 10

; bz_boxc - compose box SI (a descriptor): fill from the course, then the ball
; at [bz_px], [bz_py] with frame [bz_frm].  DS = ours.  Preserves all.
;
; SPEC.md 128.9 item 1, no MUL anywhere.  THE FILL runs COLUMN-MAJOR: down one
; word column the map entry changes only every 8 lines, so each block's run of
; lines is a jump into an unrolled `movsw / add di` chain - a map read a BLOCK,
; where wave 0 read one a word.  THE BALL takes two words and a byte a row
; through `lodsw / and / or / stosw` when the whole ball is in the box (the
; frame read at a constant distance from its mask, so one pointer walks both);
; a ball the box clips (a window edge, or the old footprint's box of two) takes
; the byte path.
bz_boxc:
    ; STKBALANCE-OK: the fill's `jmp dx` is the entry into this routine's own
    ; unrolled chain (.chain, at the run's length), not a tail call: every
    ; entry runs on to .chend and the column loop, at the same depth, and the
    ; routine pops what it pushed at .noball.  No static walk follows a
    ; computed jump into the middle of a routine (pxmaster.inc's px_quant).
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    push es
    push ds
    push ds
    pop es                      ; ES = ours: the buffer
    ; --- the course: a block row at a time, down each word column ---
    mov ax, [si + 2]            ; L0, the box's first line
    mov bx, ax
    and bx, 7
    mov dx, 8
    sub dx, bx                  ; DX = the first run's lines (to the block's end)
    shl bx, 1
    add bx, BZ_CRS_BLKOFF
    mov [bz_flo], bx            ; L0's line word in a block
    and ax, 0fff8h
    shl ax, 1
    shl ax, 1
    shl ax, 1
    shl ax, 1                   ; (L0 >> 3) * 128
    add ax, BZ_CRS_MAPOFF
    mov cx, [si]
    shl cx, 1
    add ax, cx
    mov [bz_fmp], ax            ; the map entry of (L0, x0)
    mov ax, [si + 8]
    mov [bz_fbp], ax            ; the buffer's line for the run
    mov ax, [si + 6]
    mov [bz_fln], ax            ; the lines left
    push si                     ; (the descriptor, for each run and the ball)
.run:
    cmp dx, [bz_fln]            ; the run: the block's lines, cut at the box's
    jbe .n                      ; foot - the same for every word column
    mov dx, [bz_fln]
.n:
    sub [bz_fln], dx
    mov cx, dx
    shl cx, 1
    shl cx, 1                   ; 4 bytes a chain step (the ADD's BYTE form)
    mov bx, [bz_fmp]
    mov di, [bz_fbp]
    mov bp, [bz_flo]
    shl cx, 1                   ; 8 n
    add [bz_fbp], cx            ; (the next run's buffer line)
    mov ax, 2
    sub ax, cx                  ; AX = back up the run and on a word column
    shr cx, 1
    mov dx, .chend
    sub dx, cx                  ; DX = the chain's entry for the run
    mov cx, [si + 4]            ; CX = the word columns
    mov ds, [bz_cseg]
.c:
    mov si, [bx]
    add si, bp
    jmp dx
.chain:
%rep 8
    movsw
    add di, byte BZ_BOXW * 2 - 2
%endrep
.chend:
    add di, ax
    inc bx
    inc bx
    loop .c
    push es
    pop ds                      ; DS = ours
    pop si                      ; SI = the descriptor again
    push si
    cmp word [bz_fln], 0
    je .filled
    add word [bz_fmp], BZ_CRS_ROWB
    mov word [bz_flo], BZ_CRS_BLKOFF
    mov dx, 8
    jmp .run
.filled:
    pop si
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
    jg .rows
    jmp .noball
.rows:
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
    jg .bytes
    jmp .noball
.bytes:
    mov [bz_bw], ax             ; the bytes a row
    ; the destination: buf + (py + imin - y0) * 8 + (bc + kmin - 2x0)
    mov di, [bz_py]
    add di, [bz_imin]
    sub di, [si + 2]
    shl di, 1
    shl di, 1
    shl di, 1                   ; x 8, the buffer's stride
    add di, [si + 8]
    add di, cx
    add di, [bz_kmin]
    mov ax, [si]
    shl ax, 1
    sub di, ax
    ; the first mask byte: MASKOFF + 80 s + 5 imin + kmin, s = px & 3
    mov ax, [bz_imin]
    mov cx, ax
    shl ax, 1
    shl ax, 1
    add ax, cx
    add ax, [bz_kmin]           ; AX = 5 imin + kmin
    mov dx, [bz_px]
    and dx, 3
    mov cl, 4
    shl dx, cl                  ; 16 s
    mov bx, dx
    shl dx, 1
    shl dx, 1
    add dx, bx                  ; DX = 80 s
    mov si, dx
    add si, ax
    add si, BZ_BAL_MASKOFF      ; SI = the first mask byte
    ; the frame's byte sits a constant BX past its mask's: FRMOFF - MASKOFF
    ; + (5120 - 80) s + 80 f
%if BZ_BAL_MASKSH != 80 || BZ_BAL_FRMSH != 5120 || BZ_BAL_FRMB != 80 || BZ_BAL_RB != 5
 %error "bz_boxc's shifts assume the 5 x 16 ball of SPEC.md 128.3"
%endif
    mov bx, dx
    mov cl, 6
    shl bx, cl                  ; 5120 s
    sub bx, dx                  ; 5040 s
    mov ax, [bz_frm]
    mov cl, 4
    shl ax, cl                  ; 16 f
    add bx, ax
    shl ax, 1
    shl ax, 1                   ; 64 f
    add bx, ax
    add bx, BZ_BAL_FRMOFF - BZ_BAL_MASKOFF
    mov cx, [bz_bw]
    mov ds, [bz_bseg]           ; DS = the ball from here
    cmp cx, BZ_BAL_RB
    jne .clip
    cmp bp, BZ_BAL_ROWS
    jne .clip
    mov cx, bp                  ; THE WHOLE BALL: two words and a byte a row
.whole:
    lodsw                       ; the mask (a set bit keeps the course)...
    and ax, [es:di]
    or ax, [bx + si - 2]        ; ...and the frame, pre-ANDed (SPEC.md 128.3)
    stosw
    lodsw
    and ax, [es:di]
    or ax, [bx + si - 2]
    stosw
    lodsb
    and al, [es:di]
    or al, [bx + si - 1]
    stosb
    add di, byte BZ_BOXW * 2 - BZ_BAL_RB
    loop .whole
    jmp short .noball
.clip:
    mov dx, BZ_BOXW * 2         ; A CLIPPED BALL: CX bytes of BP rows
    sub dx, cx                  ; DX = the buffer's step after a row's bytes
.crow:
    push cx
.cb:
    lodsb
    and al, [es:di]
    or al, [bx + si - 1]
    stosb
    loop .cb
    pop cx
    add si, BZ_BAL_RB
    sub si, cx
    add di, dx
    dec bp
    jnz .crow
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
; The SECOND of two boxes skips their overlap (SPEC.md 128.9 item 5): its
; lines in the band [bz_xlo, bz_xhi) of lines-left counts write only the words
; left of [bz_xa, bz_xb) and right of it - the first box already put those
; bytes there, the same bytes.  bz_mkboxes sets the band; bz_xhi = 0 is none.
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
    mov ax, [bz_xhi]            ; the overlap band is the second box's alone
    cmp si, bz_boxes + BZ_BOXD
    je .band
    xor ax, ax
.band:
    mov [bz_xact], ax
    mov ax, [si + 4]
    mov [bz_bw], ax
    mov bp, [si + 6]            ; BP = lines left
    mov ax, [si + 2]            ; the first line L
    mov cl, [bz_lsh]
    mov bx, ax
    shr ax, cl                  ; R = L >> lsh
    call bz_rbR
    mov dx, [si]
    shl dx, 1
    add dx, ax
    and dx, 1fffh               ; DX = the line's offset in its bank
    mov cx, [bz_rl]
    dec cx
    and bx, cx                  ; L & (rl-1)
    mov cl, 13
    shl bx, cl                  ; BX = the bank
    mov si, [si + 8]            ; SI = the buffer
    cmp word [bz_xact], 0
    jne .line
    mov ax, [bz_bw]             ; no band: every line whole.  The buffer's
    shl ax, 1                   ; step from a line's end to the next line's
    neg ax                      ; start (8 - 2w: 0 for a 4-word box)
    add ax, BZ_BOXW * 2
    mov [bz_bstep], ax
.whole:                         ; a card row: does it cross the ring's end?
    mov ax, [bz_bw]             ; (the same answer for all its lines - the
    shl ax, 1                   ; banks share the offset - so asked once a ROW)
    add ax, dx
    cmp ax, 2000h
    ja .wsplit
.wline:
    mov di, dx
    add di, bx
    mov cx, [bz_bw]
    rep movsw
    add si, [bz_bstep]
    dec bp
    jz .done
    add bx, 2000h               ; the next line's bank, and past the last bank
    cmp bx, [bz_bend]           ; the next card row
    jb .wline
    xor bx, bx
    add dx, [bz_rb]
    and dx, 1fffh
    jmp short .whole
.wsplit:                        ; it does: each line in two, through bz_wseg
    mov ax, dx
    mov cx, [bz_bw]
    call bz_wseg                ; (advances SI by the line)
    add si, [bz_bstep]
    dec bp
    jz .done
    add bx, 2000h
    cmp bx, [bz_bend]
    jb .wsplit
    xor bx, bx
    add dx, [bz_rb]
    and dx, 1fffh
    jmp short .whole
.done:
    pop es
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret
.line:                          ; the band (rare: two boxes that overlap)
    push si
    cmp bp, [bz_xact]           ; in the band: lines-left in (xlo, xhi]
    ja .bwhole
    cmp bp, [bz_xlo]
    jbe .bwhole
    mov cx, [bz_xa]             ; the words left of the overlap...
    jcxz .right
    mov ax, dx
    call bz_wseg
.right:
    pop si
    push si
    mov ax, [bz_xb]             ; ...and right of it
    mov cx, [bz_bw]
    sub cx, ax
    jbe .bnext
    shl ax, 1
    add si, ax
    add ax, dx
    call bz_wseg
    jmp short .bnext
.bwhole:
    mov ax, dx
    mov cx, [bz_bw]
    call bz_wseg
.bnext:
    pop si
    call .step
    jnz .line
    jmp short .done
; .next's step, for the band's loop (ZF set at the box's foot)
.step:
    add si, BZ_BOXW * 2
    add bx, 2000h
    cmp bx, [bz_bend]
    jb .bsame
    xor bx, bx
    add dx, [bz_rb]
    and dx, 1fffh
.bsame:
    dec bp
    ret

; bz_wseg - CX words (at least 1) from DS:SI to bank BX of the card (ES) at
; offset AX (mod 8KB), split where they cross the ring's end.  Advances SI;
; clobbers AX, CX, DI.
bz_wseg:
    and ax, 1fffh
    mov di, ax
    add di, bx
    neg ax
    add ax, 2000h
    shr ax, 1                   ; the words before the ring's end
    cmp ax, cx
    jae .tail                   ; all of them
    sub cx, ax
    xchg ax, cx                 ; CX = before the end, AX = after it
    rep movsw
    mov cx, ax
    mov di, bx                  ; ...and on from the bank's start
.tail:
    rep movsw
    ret
