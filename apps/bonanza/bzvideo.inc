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
BZ_VSPIN    equ 64              ; bz_vr's reads between clock samples (~3.8k clocks)
BZ_VLAT     equ 56              ; PIT counts, at most, from the sync's rise to the
                                ; clock's latch after bz_vr saw it: a turn of the
                                ; spin (in, xor, test, jnz, dec, jnz: ~60 clocks
                                ; at the 8088's fetch floor), the read that saw
                                ; it, the row-0 test and CLI (~70) and
                                ; bz_clk_sample's way to its OUT (call, push,
                                ; pushf, cli, xor, out: ~75) - ~205 clocks, 52
                                ; counts, rounded UP: a larger figure only makes
                                ; bz_latechk the more pessimistic
BZ_LBLC     equ 22 * 76         ; PIT counts from the vertical sync's END to the
BZ_LBLH     equ 82 * 63         ; first window line: the CGA's 6845 syncs 16 lines
                                ; from line 224 of 262 (R4 127, R5 6, R7 112), a
                                ; line 304 clocks = 76 counts; the Hercules field
                                ; from line 272 of 370 (R4 91, R5 2, R7 68), a
                                ; line ~254 clocks, taken as 63 counts (low, so
                                ; the budget errs short).  bz_latechk's beam.

; -----------------------------------------------------------------------------
; bz_fullscreen - the bracket proc.  DS = CS = our segment, ES = KERNEL_SEG,
; SI = our window.  bz_launch fetched the play's course and ball parts on the
; desktop ([bz_cseg], [bz_bseg]; on the Hercules already translated, SPEC.md
; 128.11.3) and set [bz_herc].
; -----------------------------------------------------------------------------
bz_fullscreen:
    cld
    OS88_ALTENTER_SEED
    ; Let the key that got us here (Enter, F, B or R) release before the mode set
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
    jc .wait
    mov al, BZ_KSC_R
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
    call bzs_open               ; the sound's arm and the course's song (128.20)
    call bz_play                ; the frame loop, until a key or the benchmark ends
    call bzs_close
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
    mov word [bz_vrport], 3dah
    mov word [bz_vrbits], 0008h ; 3DAh bit 3 HIGH: in the retrace
    mov word [bz_vrlim], 2      ; ...given up after two sub-ticks
    mov word [bz_mlim], BZ_MLIMC
    mov word [bz_lblank], BZ_LBLC
    mov si, bz_wkc              ; the wheel's beam and refresh, and the
    jmp short .wk               ; calibration's PREDICTED values until it runs
.herc:
    mov word [bz_W], 45
    mov word [bz_H], 50
    mov word [bz_rb], 90
    mov word [bz_rl], 4
    mov byte [bz_lsh], 2
    mov word [bz_bend], 8000h
    mov word [bz_crtc], 3b4h
    mov word [bz_vrport], 3bah
    mov word [bz_vrbits], 8080h ; 3BAh bit 7 LOW: in the retrace
    mov word [bz_vrlim], 3      ; ...three sub-ticks (a 50 Hz field)
    mov word [bz_mlim], BZ_MLIMH
    mov word [bz_lblank], BZ_LBLH
    mov dx, 3b4h
    mov ax, BZ_HR6 * 256 + 6
    out dx, ax
    mov ax, BZ_HR7 * 256 + 7
    out dx, ax
    mov si, bz_wkh
.wk:
    push ds
    pop es
    mov di, bz_wb0              ; (SPEC.md 128.12.5.3, 128.12.5.4)
    mov cx, BZ_WKN
    rep movsw
.wtab:
    ; the camera's limits, from the course's size (SPEC.md 128.10.8 item 4):
    ; cmax = COLS - W, rmax = BROWS * 8 lines / rl - H
    mov ax, [bz_cols]
    sub ax, [bz_W]
    mov [bz_cmax], ax
    mov ax, [bz_brows]
    mov cl, 3
    shl ax, cl
    mov cl, [bz_lsh]
    shr ax, cl
    sub ax, [bz_H]
    mov [bz_rmax], ax
                                ; W * dr for dr = -2 .. 2 (bz_tf's S)
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
; two sub-ticks (three on the Hercules).  Its time is IDLE (the bz_tv part).
; A timeout counts in [bz_tos] and the frame goes on.  A clock sample is kept
; ([bz_vsubs], [bz_vpit]) for bz_latechk, and [bz_vedge] says which:
;   1  the wait saw the sync RISE (a read outside it first).  The spin is
;      TIGHT - BZ_VSPIN reads between clock samples - and the sample is taken
;      just AFTER the read that found the sync, so it is at most one turn of
;      the spin plus the sampler's way to its latch (BZ_VLAT counts) after
;      the sync's START.  (It used to be the sample BEFORE that read, with a
;      clock sample every turn: a turn of ~840 clocks on MartyPC's 8088,
;      almost three CGA lines, where bz_latechk allowed one - the final pass
;      of wave 1 measured the row-0 probe's on-time boxes counted late.)
;   0  it found the sync already high, anywhere in its 16 lines: the sample is
;      the one taken before that first read, and its END is the late case.
;      On the CGA with a box at window row 0 pending ([bz_r0p]) that case is
;      no lead at all for the box (a 16-line box needs ~3.1k clocks ahead of
;      the beam), so the wait lets this sync go and takes the NEXT rise: the
;      frame a refresh late, never its row-0 box (wave 2's final pass,
;      SPEC.md 128.11.10.3).  The Hercules's 82 lines of blank hold the box.
; [bz_wvok] = 1 unless the wait timed out: the next frame's wheel and this
; frame's LEAD reckon from this sample (bzwheel.inc, SPEC.md 128.12.5.3).
; Preserves all but the flags.
; -----------------------------------------------------------------------------
bz_vr:
    push ax
    push bx
    push cx
    push dx
    mov byte [bz_wvok], 1
    call bz_clk_sample
    mov cx, [bz_subs]
    mov dx, [bz_vrport]
    mov bx, [bz_vrbits]
    mov byte [bz_vedge], 0
    in al, dx                   ; already in the sync: this sample is the one
    xor al, bh
    test al, bl
    jnz .high
    mov byte [bz_vedge], 1      ; outside it: spin for the rise
.spin:
    mov ah, BZ_VSPIN
.tight:
    in al, dx
    xor al, bh
    test al, bl
    jnz .rose
    dec ah
    jnz .tight
    call bz_clk_sample          ; the bound, a sample every BZ_VSPIN reads
    mov ax, [bz_subs]
    sub ax, cx
    cmp ax, [bz_vrlim]
    jb .spin
    inc word [bz_tos]           ; no retrace at all: go on regardless
    mov byte [bz_wvok], 0
    jmp short .done
.rose:
    cmp byte [bz_r0p], 0        ; a box at window row 0 (bz_r0pend): no
    je .rs                      ; interrupt until it is written - bz_tv's
    cli                         ; PUSHF, bz_tb's POPF
.rs:
    call bz_clk_sample          ; just after the rise: bz_latechk's beam
    jmp short .done
.high:
    cmp byte [bz_r0p], 0        ; (the same, the sync already high)
    je .done
    cmp byte [bz_herc], 0
    jne .hcli
.hwait:                         ; a CGA row-0 box: wait the sync out, then
    mov ah, BZ_VSPIN            ; spin for the next rise, under the same bound
.ht:
    in al, dx
    xor al, bh
    test al, bl
    jz .hlow
    dec ah
    jnz .ht
    call bz_clk_sample
    mov ax, [bz_subs]
    sub ax, cx
    cmp ax, [bz_vrlim]
    jb .hwait
    inc word [bz_tos]           ; never low: go on regardless
    mov byte [bz_wvok], 0
    jmp short .hcli
.hlow:
    mov byte [bz_vedge], 1
    jmp short .spin
.hcli:
    cli
.done:
    mov ax, [bz_subs]           ; the sample bz_latechk reckons the beam from
    mov [bz_vsubs], ax
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
    shl dx, 1                   ; DX = the first line's word in a block
    and ax, 0fff8h
    mov cl, [bz_mapsh]
    shl ax, cl                  ; (L0 >> 3) * ROWB: the block row's map
    add ax, BZC_MAP
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
    mov cl, [bz_mapsh]
    shl ax, cl                  ; (L0 >> 3) * ROWB
    add ax, BZC_MAP
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
    add si, dx
    add si, dx                  ; SI = the first line's word
    shr dl, 1
    neg dl
    add dl, 4                   ; DL = the rows left in this block (1..4)
    cmp dl, 4
    jne .cseg
    sub bx, [BZC_ROWB]          ; at the block's top: the block loop loads it
    mov dl, 0                   ; (ROWB read through DS = the part, 128.10.6.4)
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
    add bx, [BZC_ROWB]          ; the next block row
    mov si, [bx]
    BZ_CROW
    BZ_CROW
    BZ_CROW
    BZ_CROW
    loop .cblk
.ctail:
    mov al, dl
    or al, al
    jz .cnext
    add bx, [BZC_ROWB]
    mov si, [bx]
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
    add si, dx
    add si, dx
    cmp dl, 4                   ; the first line in the block's second row:
    jae .hseg1                  ; one row left in it
    sub bx, [BZC_ROWB]          ; at the block's top: the block loop loads it
.hseg:
    mov dl, cl                  ; whole blocks (two rows), then a tail
    and dl, 1
    shr cx, 1
    jcxz .htail
.hblk:
    add bx, [BZC_ROWB]
    mov si, [bx]
    BZ_HROW
    BZ_HROW
    loop .hblk
.htail:
    or dl, dl                   ; DL = 1: the run ends inside a block
    jz .hnext
    add bx, [BZC_ROWB]
    mov si, [bx]
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
; THE BOXES (SPEC.md 128.4, 128.11.10).  A box is a rectangle of the world in
; WORDS x LINES, composed in RAM from the course, the shadow, the ball's sprite
; and the occluders that lay back over them, and then written to the card a
; line at a time.  Descriptor, BZ_BOXD bytes: +0 x0 (world word column), +2 y0
; (world line), +4 w (words), +6 h (lines), +8 the buffer, +10 the overlap
; band's xhi (0: none), +12 xlo, +14 xa, +16 xb (bz_boxw), +18 the box's
; GROUP (0 the ball's, 1 the shadow's, 2 the contact's), +19 unused.  At most four boxes a
; frame (bzgame.inc bz_mkboxes).  A buffer's lines are BZ_BOXW words apart
; whatever the box's w (SPEC.md 128.9 item 1: a fixed stride is what lets the
; fill and the sprite step by a constant).  A buffer holds BZ_BOXL lines (the
; RIDE BOX and the slab's box after a waited frame, SPEC.md 128.13.4.1,
; 128.13.4.3); every union but the platform's is held to BZ_BOXH.
; -----------------------------------------------------------------------------
BZ_BOXW     equ 4               ; words (8 bytes)
BZ_BOXH     equ 24              ; lines: the union limit of every group but the platform's
BZ_BOXL     equ 32              ; lines: the platform's union limit, and a buffer's
BZ_BOXB     equ BZ_BOXW * 2 * BZ_BOXL
BZ_BOXD     equ 20

; bz_boxc - compose box SI (a descriptor): fill from the course, then the
; slab when it is under the ball (bz_pov 0, bzwheel.inc bz_pblit), the
; shadow when it is drawn this frame (bz_snv: AND only), then the ball's
; sprite - each clipped to the box (bz_blit).  The occluders are laid after
; every box is composed, once a frame (bz_occ), and the slab over the ball
; after them (bz_pover).  DS = ours.  Preserves all.
;
; SPEC.md 128.9 item 1, no MUL anywhere.  THE FILL runs COLUMN-MAJOR: down one
; word column the map entry changes only every 8 lines, so each block's run of
; lines is a jump into an unrolled `movsw / add di` chain - a map read a BLOCK,
; where wave 0 read one a word.
bz_boxc:
    ; STKBALANCE-OK: the fill's `jmp dx` is the entry into this routine's own
    ; unrolled chain (.chain, at the run's length), not a tail call: every
    ; entry runs on to .chend and the column loop, at the same depth, and the
    ; routine pops what it pushed at .done.  No static walk follows a
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
    mov [bz_flo], bx            ; L0's line word in a block
    and ax, 0fff8h
    mov cl, [bz_mapsh]
    shl ax, cl                  ; (L0 >> 3) * ROWB
    add ax, BZC_MAP
    mov cx, [si]
    shl cx, 1
    add ax, cx
    mov [bz_fmp], ax            ; the map entry of (L0, x0)
    mov ax, [si + 8]
    mov [bz_fbp], ax            ; the buffer's line for the run
    mov ax, [si + 6]
    mov [bz_fln], ax            ; the lines left
    push si                     ; (the descriptor, for each run and the sprite)
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
    mov ax, [bz_rowb]           ; the next block row: ROWB, the launch's
    add [bz_fmp], ax            ; copy (128.10.6.4)
    mov word [bz_flo], 0
    mov dx, 8
    jmp .run
.filled:
    pop si
    ; --- the slab when it is UNDER the ball (SPEC.md 128.12.4.5; over it,
    ; bz_pover lays it after the occluders) ---
    cmp byte [bz_pov], 0
    jne .shadow
    call bz_pblit
.shadow:
    ; --- the shadow, AND only (SPEC.md 128.11.10.2: before the ball) ---
    cmp byte [bz_snv], 0
    je .ball
    mov ax, [bz_spy]
    mov dx, BZ_BAL_SHDROWS
    mov di, [bz_shm]
    xor bx, bx
    call bz_blit
.ball:
    ; --- the ball's sprite: mask AND, frame OR; none while it is hidden in a
    ; tube (SPEC.md 128.12.6.1) ---
    cmp byte [bz_tube], 0
    jne .nob
    mov ax, [bz_py]
    mov dx, BZ_BAL_ROWS
    mov di, [bz_smsk]
    mov bx, [bz_sfd]
    call bz_blit
.nob:
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

; bz_blit - a sprite of the ball part into box SI, clipped to it: its rows i
; at world lines AX + i, i < DX, its 5 bytes a row from world byte px / 4 (the
; ball's columns: the sprite and the shadow share them).  Row i, byte k of the
; MASK is at DI + 5 i + k in the ball part, the FRAME's BX past it (frames are
; pre-ANDed, SPEC.md 128.3) - or, BX = 0, no frame: AND only (the shadow).
; A SET mask bit keeps the box.  The whole sprite inside the box takes two
; words and a byte a row (`lodsw / and / or / stosw`), and the shadow whole
; across the same with AND alone; a sprite clipped anywhere, or a shadow
; clipped across, the byte path.  DS = ES = ours.  Preserves all but AX, BX, CX, DX,
; DI, BP.
bz_blit:
    push si
    mov [bz_bly], ax
    mov [bz_blm], di
    mov bp, bx                  ; BP = the frame's distance (0: none)
    ; rows i in [imin, imax): AX + i inside [y0, y0 + h)
    mov cx, [si + 2]
    sub cx, ax                  ; y0 - y
    jge .imin
    xor cx, cx
.imin:
    mov [bz_imin], cx
    mov ax, [si + 2]
    add ax, [si + 6]
    sub ax, [bz_bly]            ; y0 + h - y
    cmp ax, dx
    jle .imax
    mov ax, dx
.imax:
    sub ax, cx
    jg .rows
    jmp .out
.rows:
    mov dx, ax                  ; DX = the rows
    ; bytes k in [kmin, kmax): px/4 + k inside [2x0, 2x0 + 2w)
    mov cx, [bz_px]
    shr cx, 1
    shr cx, 1                   ; CX = the sprite's first world byte
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
    jmp .out
.bytes:
    mov [bz_bw], ax             ; the bytes a row
    ; the destination: buf + (y + imin - y0) * 8 + (bc + kmin - 2x0)
    mov di, [bz_bly]
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
    ; the first mask byte: the mask's row 0 + 5 imin + kmin
    mov ax, [bz_imin]
    mov si, ax
    shl ax, 1
    shl ax, 1
    add si, ax
    add si, [bz_kmin]
    add si, [bz_blm]
%if BZ_BAL_RB != 5
 %error "bz_blit's rows assume the 5-byte rows of SPEC.md 128.3"
%endif
    mov bx, bp
    mov cx, [bz_bw]
    mov ds, [bz_bseg]           ; DS = the ball part from here
    or bx, bx
    jz .andonly
    cmp cx, BZ_BAL_RB
    jne .clip
    cmp dx, BZ_BAL_ROWS
    jne .clip
    mov cx, dx                  ; THE WHOLE SPRITE: two words and a byte a row
.whole:
    lodsw                       ; the mask (a set bit keeps the box)...
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
    jmp short .ds
.clip:
    mov bp, BZ_BOXW * 2         ; A CLIPPED SPRITE: CX bytes of DX rows
    sub bp, cx                  ; BP = the buffer's step after a row's bytes
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
    add di, bp
    dec dx
    jnz .crow
    jmp short .ds
.andonly:
    cmp cx, BZ_BAL_RB           ; THE SHADOW: AND only.  Unclipped across, two
    jne .aclip                  ; words and a byte a row (any rows: the row's
.awhole:                        ; bytes are what the word path saves)
    lodsw
    and [es:di], ax
    inc di
    inc di
    lodsw
    and [es:di], ax
    inc di
    inc di
    lodsb
    and [es:di], al
    add di, byte BZ_BOXW * 2 - BZ_BAL_RB + 1
    dec dx
    jnz .awhole
    jmp short .ds
.aclip:
    mov bp, BZ_BOXW * 2         ; ...clipped across: CX bytes of DX rows
    sub bp, cx
.arow:
    push cx
.ab:
    lodsb
    and [es:di], al
    inc di
    loop .ab
    pop cx
    add si, BZ_BAL_RB
    sub si, cx
    add di, bp
    dec dx
    jnz .arow
.ds:
    push es
    pop ds                      ; DS = ours
.out:
    pop si
    ret

; bz_occ - THE OCCLUDER PASS (SPEC.md 128.10.8 item 1, 128.10.4.4, 128.11.10.2),
; ONCE A FRAME, after every box is composed: every record the rule lays at the
; ball's position lays its block's pixels back over the shadow and the ball in
; EVERY box it meets, `buffer = (buffer AND mask) OR (block AND NOT mask)`,
; done as `((buffer XOR block) AND mask) XOR block` - a SET mask bit keeps the
; buffer, so no NOT.  The rule, for a record (s_C, top_C):
;
;     lay it  iff  s_b < s_C  and  z_b + m < top_C
;
; s_b = [bz_sb] (bz_camera's, this frame), z_b = the integer px of bz_gz, m =
; BZ_CLIMB grounded and 0 airborne.  The verdicts depend on the ball alone, so
; the NEW footprint's blocks are walked ONCE - its lines [py, py + 16) and word
; columns [nfx0, nfx1], each clipped to the window, so at most 3 x 3 blocks -
; and each laid group goes into every box that meets it (bz_olay), clipped to
; the box: two boxes that overlap hold the same bytes there.  A block row's
; records come from OCCIDX in their sorted order (column, then s_C): a binary
; search finds the first at or right of the first column and the walk stops
; at the first right of the last.  The records of one block word are a GROUP:
; their laid masks are ANDed (bz_oand) and the word is laid ONCE a box
; (bz_olay), so a frame lays at most 3 x 3 words a box whatever the record
; counts (128.10.9).  Outside the footprint a box holds the course and the
; shadow already, and with OCCG clear (the shadow's condition) no record lays
; over the shadow alone, so laying a record's whole word is laying its
; footprint pixels.
;
; THE GATE: the pass runs only when [bz_ogate] (bz_mkboxes: the centre's cell
; has OCC, the grid's flag - some position in the cell meets a record the rule
; would lay - for an AIRBORNE ball, or OCCG - some GROUNDED ball in the cell
; does - for a grounded one, or a harness POKED the ball, bz_pokd, when the window is behind
; until the next step and the pass runs ungated, which lays what the rule
; lays, the flag being only a saving).  DS = ours.  Preserves all.
bz_occ:
    cmp byte [bz_ogate], 0
    jne .gate
    ret
.gate:
    push ax
    inc word [bz_nocf]
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    push ds
    push es
    mov bx, [bz_wtop]           ; the lines: [max(py, top), min(py + 16, top
    mov ax, [bz_py]             ; + BZ_LINES))
    cmp ax, bx
    jge .lo
    mov ax, bx
.lo:
    mov [bz_olo], ax
    add bx, BZ_LINES
    mov dx, [bz_py]
    add dx, BZ_BAL_ROWS
    cmp dx, bx
    jle .hi
    mov dx, bx
.hi:
    mov [bz_ohi], dx
    cmp ax, dx
    jge .out0
    mov bx, [bz_c0n]            ; the columns: DL = max(nfx0, c0), DH =
    mov ax, [bz_nfx0]           ; min(nfx1, c0 + W - 1) (both < 128)
    cmp ax, bx
    jge .c0
    mov ax, bx
.c0:
    mov dl, al
    add bx, [bz_W]
    dec bx
    mov ax, [bz_nfx1]
    cmp ax, bx
    jle .c1
    mov ax, bx
.c1:
    mov dh, al
    cmp dl, dh
    jbe .key
.out0:
    jmp .out
.key:
    mov ax, [bz_gz + 1]         ; the key: z_b + m
    cmp byte [bz_air], 0
    jne .air
    add ax, BZ_CLIMB
.air:
    mov [bz_ozk], ax
    mov ax, [bz_olo]
    and al, 0f8h
    mov [bz_obr], ax            ; the first block row's first line
    push ds
    pop es                      ; ES = ours
    mov ds, [bz_cseg]           ; DS = the course part
.brow:
    mov bx, [es:bz_obr]         ; OCCIDX[B / 8]: the row's records [SI, BP)
    shr bx, 1
    shr bx, 1
    add bx, [BZC_OCCIDX]
    mov si, [bx]
    mov bp, [bx + 2]
    mov bx, bp                  ; the first record at or right of column DL:
.bs:                            ; a lower bound over [SI, BX), 8 bytes a
    mov ax, bx                  ; record (an empty row costs one test)
    sub ax, si
    jz .bsd
    shr ax, 1
    and ax, byte -8             ; 8 floor(n / 2)
    mov di, si
    add di, ax                  ; DI = the middle record
    cmp [di], dl
    jae .bsh
    lea si, [di + 8]
    jmp short .bs
.bsh:
    mov bx, di
    jmp short .bs
.bsd:
    cmp si, bp
    jae .nrow0                  ; none at or right of DL
    mov al, [si]
    cmp al, dh
    jbe .lines                  ; the first is right of DH: none in the
.nrow0:                         ; footprint's columns
    jmp .nrow
.lines:
    mov ax, [es:bz_obr]         ; the block row's lines inside [lo, hi):
    mov bx, [es:bz_olo]         ; [max(lo, B), min(hi, B + 8))
    cmp bx, ax
    jge .f
    mov bx, ax
.f:
    add ax, 8
    mov di, [es:bz_ohi]
    cmp di, ax
    jle .e
    mov di, ax
.e:
    sub di, bx
    mov [es:bz_on], di
    mov [es:bz_of], bx
    and bx, 7
    shl bx, 1
    mov [es:bz_ofl2], bx        ; 2 x the first line's place in the block
    mov ax, [es:bz_obr]         ; the map row: MAP + (B << MAPSH), as the fill's
    mov cl, [es:bz_mapsh]
    shl ax, cl
    add ax, BZC_MAP
    mov [es:bz_omrow], ax
    mov cx, [es:bz_sb]          ; the walk's keys in registers: CX = s_b,
    mov di, [es:bz_ozk]         ; DI = z_b + m
    push dx                     ; (DL, the first column, is the next row's)
.grp:
    mov dl, [si]                ; A GROUP: the records of one block word, its
    xor bx, bx                  ; laid masks ANDed - BX: 0 none laid yet, a
.rec:                           ; mask's offset, or -1 for bz_omsk
    cmp cx, [si + 2]
    jge .skip                   ; s_b >= s_C: beside or in front
    cmp di, [si + 4]
    jge .skip                   ; z_b + m >= top_C: above it
    inc word [es:bz_nlay]       ; LAID
    or bx, bx
    jnz .and
    mov bx, [si + 6]            ; the group's first: its own mask
    jmp short .skip
.and:
    call bz_oand                ; a second or later: ANDed into bz_omsk
.skip:
    add si, 8
    cmp si, bp
    jae .gend
    mov al, [si]
    cmp al, dl
    je .rec                     ; the same block word
.gend:
    or bx, bx
    jz .gnext
    call bz_olay                ; the word's lines laid ONCE a box (128.10.9)
.gnext:
    cmp si, bp
    jae .rdone
    mov al, [si]
    cmp al, dh
    jbe .grp                    ; the stop: the first right of the last column
.rdone:
    pop dx
.nrow:
    mov ax, [es:bz_obr]
    add ax, 8
    mov [es:bz_obr], ax
    cmp ax, [es:bz_ohi]
    jge .out
    jmp .brow
.out:
    pop es
    pop ds
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; bz_oand - a group's second or later laid record, SI, ANDed into bz_omsk:
; BX = the group's mask so far (a part offset, or -1 for bz_omsk already) ->
; BX = -1.  Only the lines the pass lays ([bz_ofl2 / 2, + bz_on), at the
; same place in bz_omsk as in a mask); the AND of two keep-masks keeps only
; what both keep, so laying it once is laying each in turn (128.10.8 item 1).
; DS = the course part, ES = ours.  Preserves all but AX and BX.
bz_oand:
    push cx
    push si
    push di
    mov cx, [es:bz_on]
    mov ax, [es:bz_ofl2]
    mov si, [si + 6]
    add si, ax                  ; SI = this record's mask line
    mov di, bz_omsk
    add di, ax                  ; DI = bz_omsk's
    cmp bx, byte -1
    je .and
    add bx, ax                  ; the group's first: BX = its mask line, and
.both:                          ; bz_omsk = the two ANDed
    lodsw
    and ax, [bx]
    stosw
    inc bx
    inc bx
    loop .both
    mov bx, -1
    jmp short .done
.and:
    lodsw
    and [es:di], ax
    inc di
    inc di
    loop .and
.done:
    pop di
    pop si
    pop cx
    ret

; bz_olay - lay a group into EVERY box it meets: block word DL of the block row
; bz_occ is on, its lines [bz_of, + bz_on) (2 x the first's place in the
; block: bz_ofl2), under mask BX (a part offset, or -1 for bz_omsk), each box
; taking the lines and the word it holds: buffer = ((buffer XOR block) AND
; mask) XOR block.  DS = the course part, ES = ours.  Preserves all but AX and
; BX.
bz_olay:
    push cx
    push dx
    push si
    push di
    push bp
    mov bp, bx                  ; BP = the mask
    mov bl, dl
    xor bh, bh
    shl bx, 1
    add bx, [es:bz_omrow]
    mov ax, [bx]
    mov [es:bz_oblk], ax        ; the block (an absolute offset)
    mov si, bz_boxes
    mov cx, [es:bz_nbox]
.box:
    push cx
    mov al, dl                  ; the word inside the box: DI = 2 (c - x0)
    xor ah, ah
    sub ax, [es:si]
    cmp ax, [es:si + 4]
    jae .nb                     ; (unsigned: left of x0 is huge)
    shl ax, 1
    mov di, ax
    mov ax, [es:bz_of]          ; the lines: [max(f, y0), min(f + n, y0 + h))
    mov bx, [es:si + 2]
    cmp ax, bx
    jge .l0
    mov ax, bx
.l0:
    mov cx, [es:bz_of]
    add cx, [es:bz_on]
    add bx, [es:si + 6]
    cmp cx, bx
    jle .l1
    mov cx, bx
.l1:
    sub cx, ax
    jle .nb                     ; CX = the lines
    mov bx, ax
    sub bx, [es:si + 2]
    shl bx, 1
    shl bx, 1
    shl bx, 1
    add di, bx
    add di, [es:si + 8]         ; DI = the buffer's word
    and ax, 7
    shl ax, 1                   ; 2 x the first line's place in the block
    mov bx, [es:bz_oblk]
    add bx, ax                  ; BX = the block's line
    push si
    cmp bp, byte -1
    je .scr
    mov si, bp
    add si, ax                  ; SI = the mask's line
.line:
    mov ax, [es:di]
    xor ax, [bx]
    and ax, [si]
    xor ax, [bx]
    stosw
    add di, byte BZ_BOXW * 2 - 2
    inc bx
    inc bx
    inc si
    inc si
    loop .line
    jmp short .bd
.scr:
    mov si, bz_omsk
    add si, ax
.sline:
    mov ax, [es:di]
    xor ax, [bx]
    and ax, [es:si]
    xor ax, [bx]
    stosw
    add di, byte BZ_BOXW * 2 - 2
    inc bx
    inc bx
    inc si
    inc si
    loop .sline
.bd:
    pop si
.nb:
    pop cx
    add si, BZ_BOXD
    dec cx
    jz .done
    jmp .box
.done:
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    ret

; bz_boxw - box SI (a descriptor) to the card, a line at a time, each line
; split where it crosses the ring's 8KB end.  DS = ours.  Preserves all.
; The LATER of two boxes of one group skips their overlap (SPEC.md 128.9 item
; 5, 128.11.10.2): its lines in the band (xlo, xhi] of lines-left counts write
; only the words left of [xa, xb) and right of it - the earlier box already
; put those bytes there, the same bytes.  bz_mkboxes sets the band in the
; descriptor (+10 .. +16); xhi = 0 is none.
;
; THE WHOLE-ROW PATH (SPEC.md 128.13.4.4): a box with no band, 3 or 4 words
; wide, writes each card row it covers from the row's FIRST line by an
; unrolled block - the CGA's two lines, the Hercules' four, `movsw` x w a
; line, the bank's step folded into an `add di` and the buffer's (2 bytes a
; line for a 3-word box) into `inc si` - the ring's end tested once a card
; row, as the per-line loop does (a crossing row goes to bz_wseg).  A row the
; box starts or ends inside, and any other width, take the per-line loop.
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
    mov ax, [si + 10]           ; the band, copied: SI is the buffer below
    mov [bz_xact], ax
    or ax, ax
    jz .band
    mov ax, [si + 12]
    mov [bz_xlo], ax
    mov ax, [si + 14]
    mov [bz_xa], ax
    mov ax, [si + 16]
    mov [bz_xb], ax
.band:
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
    je .nob
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
    jmp .done
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
.nob:
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
    or bx, bx                   ; from the row's first line, a whole row or
    jnz .wline                  ; more left, 3 or 4 words: the whole-row path
    cmp bp, [bz_rl]
    jb .wline
    mov ax, [bz_bw]
    sub ax, 3
    cmp ax, 1
    jbe .fast
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
.fast:                          ; the whole-row path (bz_bwrows), then the
    call bz_bwrows              ; lines it left: a partial last row, or a row
    or bp, bp                   ; crossing the ring's end (bz_wseg's)
    jz .done
    jmp .whole

; bz_bwrows - bz_boxw's WHOLE-ROW PATH (SPEC.md 128.13.4.4): from DX, the
; offset of a card row's first line (bank 0, BX = 0), the whole card rows of
; BP lines left for a box AX + 3 words wide (AX = 0, 1), DS:SI its buffer, ES
; the card: each card row by an unrolled block, the ring's end tested once a
; row.  -> BP the lines it left (a partial last row, or every line from a row
; that would cross the ring's end on), DX that row's offset, BX = 0, SI past
; what it wrote.  Clobbers AX, CX, DI.
bz_bwrows:
    ; STKBALANCE-OK: the blocks' `jmp bp` is the loop back into this routine's
    ; own blocks (bz_bwft: one card row a turn), not a tail call - every block
    ; runs on to .ftail and leaves through .fx, which pops what the entry
    ; pushed and returns.  No static walk follows a register jump (bz_boxc's
    ; `jmp dx` is the same shape).
    mov cl, [bz_lsh]            ; 1 the CGA, 2 the Hercules
    add al, cl
    add al, cl
    cbw
    shl ax, 1
    xchg ax, di                 ; DI = (w - 3 + 2 lsh) x 2: the block's entry
    mov ax, bp
    shr ax, cl
    xchg ax, cx                 ; CX = the whole card rows left
    mov ax, [bz_rl]
    dec ax
    and bp, ax
    push bp                     ; the lines after them (0 .. rl - 1)
    mov bp, [bz_bwft - 4 + di]  ; BP = the block, a card row a turn
    mov bx, [bz_bw]
    shl bx, 1
    neg bx
    add bh, 20h                 ; BX = 2000h - 2 w: a row starting past it
    mov ax, [bz_rb]             ; crosses the ring's end
    jmp bp
.fx:                            ; CX rows left (a crossing row stopped the
    mov ax, cx                  ; blocks, or 0): back into the line count
    mov cl, [bz_lsh]
    shl ax, cl
    pop bp
    add bp, ax
    xor bx, bx                  ; (the next row's first line)
    ret
; the blocks: one card row from offset DX, its first line in bank 0; the
; Hercules' first two lines run on into the CGA's two
%macro BZ_BWLN 1                ; one line of %1 words, DI past it ...
 %rep %1
    movsw
 %endrep
 %rep 2 * (BZ_BOXW - %1)
    inc si                      ; (the buffer's stride is BZ_BOXW words)
 %endrep
%endmacro
%macro BZ_BWNX 1                ; ... and on to the next bank's line
    add di, 2000h - 2 * %1
%endmacro
.fh3:
    mov di, dx
    BZ_BWLN 3
    BZ_BWNX 3
    BZ_BWLN 3
    BZ_BWNX 3
    jmp short .c3
.fc3:
    mov di, dx
.c3:
    BZ_BWLN 3
    BZ_BWNX 3
    BZ_BWLN 3
    jmp short .ftail
.fh4:
    mov di, dx
    BZ_BWLN 4
    BZ_BWNX 4
    BZ_BWLN 4
    BZ_BWNX 4
    jmp short .c4
.fc4:
    mov di, dx
.c4:
    BZ_BWLN 4
    BZ_BWNX 4
    BZ_BWLN 4
.ftail:
    add dx, ax                  ; the next card row
    and dh, 1fh
    dec cx
    jz .fx
    cmp dx, bx
    ja .fx                      ; (it crosses the ring's end: bz_wseg's)
    jmp bp

bz_bwft:                        ; bz_bwrows's blocks, by w - 3 + 2 lsh
    dw bz_bwrows.fc3, bz_bwrows.fc4, bz_bwrows.fh3, bz_bwrows.fh4
%if BZ_BOXW != 4
 %error "bz_boxw's whole-row path writes 3- and 4-word boxes of a 4-word stride"
%endif

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
