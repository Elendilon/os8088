; bzvideo.inc - BONANZA's bracket, mode, retrace wait, ring writers and boxes
; (SPEC.md 130.2, 130.4).  Shapes from Excitebike's CGA/Hercules engine
; (apps/excitebike/cga.inc, herc.inc, SPEC.md 102), made two-dimensional.
;
; THE RING (SPEC.md 130.2).  On both cards the 6845's start address S counts
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
; by the bonanzaperf row and wave 0b's optimisation round (SPEC.md 130.9 items
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
; 130.11.3) and set [bz_herc].
; -----------------------------------------------------------------------------
bz_fullscreen:
    cld
    OS88_ALTENTER_SEED
    call bz_fload               ; wave 8c (130.19.8): the cards' glyphs, while
                                ; the desktop's font is still legal to ask
    ; Let the key that got us here (Enter, F, B, R or D) release before the mode set
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
    jc .wait
    mov al, BZ_KSC_D            ; (D, the demo benchmark, 130.14.7.3)
    call OSAPI_KEY_DOWN
    jnc .mode
.wait:
    mov al, FSXW_FRAME
    call OSAPI_FSX_WAIT
    loop .release
.mode:
    call bz_adapter             ; the display must still be the one the desktop
    cmp al, [bz_cardk]          ; fetched the parts for
    jne .moved
    mov bx, bz_fsxm - 1
    xlat                        ; AL = the card's mode (130.46.2)
.set:
    push ds
    pop es
    mov di, bz_fsi
    call OSAPI_FSX_MODE
    jc .refused
    mov byte [bz_fs], 1
%if BZ_PATH_NPAD
    cmp byte [bz_ingame], 0     ; wave 8b (130.19.5): THE GAME - the pathway
    je .one                     ; and its courses, round after round, in
 %if BZ_TITLE
    cmp byte [bz_ingame], 2     ; (SPEC.md 130.23.4: THE TITLE's rounds, the
    jne .g8                     ; game among them)
    call bz_tround
    jmp short .leave
.g8:
 %endif
    call bz_grounds             ; this one bracket (bonanza.asm)
    jmp short .leave
.one:
%endif
    call bz_vinit
    call bzs_open               ; the sound's arm and the course's song (130.20)
    call bz_play                ; the frame loop, until a key or the benchmark ends
    call bz_post                ; the bests, the held log's line, the face's page: memory
    call bzs_close              ; only, before the kernel's restore paints it
.leave:
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
bz_fsxm:    db FSXM_CGA320, FSXM_HERC, FSXM_VGA0D ; bz_card's modes

; -----------------------------------------------------------------------------
; bz_vinit - the card's geometry, after OSAPI_FSX_MODE.  The Hercules is put on
; Excitebike's 200-line field (R6 = 50, R7 = 68).  On the CGA first the
; course's COLOUR SELECT (wave 6, SPEC.md 130.16.6): its BZ_CRS_PALS byte to
; port 3D9h, the one write, labelled bz_vinit.vpal (a row breaks on it through
; os88sym), since the mode set leaves the BIOS's 30h.  Never on the Hercules,
; whose picture is a function of the colour INDEX.  On an EGA or VGA that
; came up VID_CGA no register answers 3D9h and the BIOS's palette stays: a
; cosmetic loss, no wrong pixel (130.16.6).  PALETTE 2 (bit 6) is mode 5's
; cyan, red, white: the mode control register's B/W bit, which bz_cmode
; carries into bz_blank and bz_unblank - the play's first frame is a full
; write, so its bz_unblank lights the card in it.  Preserves nothing.
; -----------------------------------------------------------------------------
bz_vinit:
    mov byte [bz_cmode], 2ah    ; (mode 4's; the Hercules's and VGA's too)
    mov ax, [bz_fsi + FSI_SEG]
    mov [bz_vseg], ax
    mov word [bz_smask], 0fffh  ; (the 6845's ring; the VGA's part sets 0FFFFh)
    cmp byte [bz_vga], 0        ; THE VGA: its half is the part's (SPEC.md
    je .nvga                    ; 130.46.3), every variable below and its ports
    mov bl, [bz_crs]            ; ...and the course's LOCK (130.45.2 item 1):
    xor bh, bh                  ; the CGA's byte, its 320 px framing, as the
    shl bx, 1                   ; VGA window's column less one (the display
    mov al, [bz_clocks + bx]    ; on the window's middle: x0 = lock 8;
    cbw                         ; 130.46.12), FFFFh none
    or ax, ax
    js .vl
    dec ax
    jns .vl
    xor ax, ax
.vl:
    mov [bz_lockc], ax
    BZ_VCALL BZV_INIT
    jmp bz_vstop                ; ...and the STOPS (130.45.4, 130.45.5) on the
                                ; part's limits (a VGA row a line: bz_rl 1)
.nvga:
    cmp byte [bz_herc], 0
    jne .herc
    mov bl, [bz_crs]            ; the CGA: the course's colour select
    xor bh, bh
    mov al, [bz_cpals + bx]
    mov dx, 3d9h
.vpal:
    out dx, al
    test al, 40h                ; palette 2: mode 5's B/W bit (130.16.6)
    jz .m4
    or byte [bz_cmode], 4
.m4:
    mov word [bz_W], BZ_WC
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
    mov word [bz_W], BZ_WH
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
    mov di, bz_wb0              ; (SPEC.md 130.12.5.3, 130.12.5.4)
    mov cx, BZ_WKN
    rep movsw
.wtab:
    ; the camera's limits, from the course's size (SPEC.md 130.10.8 item 4):
    ; cmax = COLS - W, rmax = BROWS * 8 lines / rl - H
    mov ax, [bz_cols]
    sub ax, [bz_W]
    mov [bz_cmax], ax
    mov bl, [bz_crs]            ; SPEC.md 130.45.2 item 1: the course's LOCK
    xor bh, bh                  ; on this card, FFFFh none
    shl bx, 1
    add bl, [bz_herc]
    adc bh, 0
    mov al, [bz_clocks + bx]
    cbw                         ; (FFh -> FFFFh; a c0 is at most cmax, < 80h)
    mov [bz_lockc], ax
    mov ax, [bz_brows]
    mov cl, 3
    shl ax, cl
    mov cl, [bz_lsh]
    shr ax, cl
    sub ax, [bz_H]
    mov [bz_rmax], ax
    call bz_vstop               ; SPEC.md 130.45.4, 130.45.5: the STOPS
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
; bz_vstop - the course's camera STOPS folded into the limits bz_vinit has just
; set from its size (SPEC.md 130.45.4 - 130.45.6; bbcourse.cam_limits,
; cam_span), on any card (bz_rl, bz_lsh and bz_W the card's): the rows' range
; is kept twice - the picture's, 0 - bz_rfmx (the part's rmax), and the
; STOPPED one, bz_rsmn - bz_rsmx: the BOTTOM LINE B (BZ_CRS_BOTS, 0 none) caps
; rmax at ceil((B - BZ_LINES) / rl), at least 0, BZ_CRS_STOPS' t sets rmin =
; 8 t >> lsh - which bz_clampwin / bz_clampmv choose between each frame by the
; window's column against the SPAN (BZ_CRS_SPANS' a b: bz_sglo = b - W, bz_sghi
; = a; 255 0 none, every column); its l and r set cmin = l and take r off
; cmax; the PULL bz_kpull = 4 >> lsh rows.  The stopped range goes in
; bz_rmin, bz_rmax too, where a course with no span (a 255, every course but
; one) keeps it: bz_clampmv's every frame there is the clamp before the span
; (SPEC.md 130.45.6, its cost).  0 is each stop byte's identity and the
; tool holds every range whole on every card, so neither the bytes nor a
; course without them needs a branch or a clamp.  Clobbers AX, BX, CL, DX,
; SI, DI.
; -----------------------------------------------------------------------------
bz_vstop:
    mov bl, [bz_crs]
    xor bh, bh
    mov si, bx
    shl bx, 1
    mov cl, [bz_lsh]
    mov di, bz_rmin             ; (BZR_*)
    mov dx, [di + 2]            ; DX = the picture's most (bz_rmax) ...
    mov [di + BZR_FMX], dx
    mov ax, [bz_cbots + bx]     ; ... less the BOTTOM STOP: the window's
    or ax, ax                   ; foot never passes the course's bottom line
    jz .nbot
    sub ax, BZ_LINES
    jns .bpos
    xor ax, ax
.bpos:
    add ax, [bz_rl]
    dec ax
    shr ax, cl
    cmp ax, dx
    jge .nbot
    xchg ax, dx
.nbot:
    mov [di + BZR_SMX], dx      ; (and in bz_rmin, bz_rmax: a course with no
    mov [di + 2], dx            ; span keeps them, bz_clampwin sets a span's)
    mov dx, [bz_cspans + bx]    ; the SPAN: DL a, DH b
    mov al, dh
    xor ah, ah
    sub ax, [bz_W]
    mov [di + BZR_SLO], ax      ; b - W
    xor dh, dh
    mov [di + BZR_SHI], dx      ; a
    mov ax, 4                   ; the PULL: four lines, in rows
    shr ax, cl
    mov [di + BZR_PULL], ax
    lea si, [bz_cstops + bx + si] ; (3 bytes a course)
    lodsb                       ; t: the TOP stop, block rows
    xor ah, ah
    shl ax, 1
    shl ax, 1
    shl ax, 1
    shr ax, cl
    mov [di + BZR_SMN], ax
    mov [di], ax
    lodsb                       ; l: the LEFT stop, a column
    xor ah, ah
    mov [bz_cmin], ax
    lodsb                       ; r: the RIGHT stop, columns off cmax (AH 0)
    sub [bz_cmax], ax
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
; bz_vr - the retrace wait (SPEC.md 130.4): the CGA's 3DAh bit 3 high, the
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
;      SPEC.md 130.11.10.3).  The Hercules's 82 lines of blank hold the box.
; [bz_wvok] = 1 unless the wait timed out: the next frame's wheel and this
; frame's LEAD reckon from this sample (bzwheel.inc, SPEC.md 130.12.5.3).
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
; 130.9 item 4).  NO FASTER than that MUL: with the call, the push/pop and
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
; bz_row - THE ROW WRITER (SPEC.md 130.2 rules 1 and the full write): world
; card row AX, world word columns BX .. BX+CX-1 (CX at least 1), every line of
; the row (2 on the CGA, 4 on the Hercules), each word drawn from the course:
; the word of (map[L>>3][c] + 2*(L&7)).  DS = ours on entry.  Preserves every
; register.  [bz_nrow] counts the calls (a harness also counts entries at this
; global label).
;
; WORD COLUMNS OUTERMOST (SPEC.md 130.9 item 3): a row's lines all come from
; the same block row, so each word column's map entry is read ONCE and its 2
; (4) line words go to the 2 (4) banks at the same offset - wave 0 read the map
; once a LINE, twice (four times) a word.  A row is contiguous in every bank
; at one offset, so the only split is where it crosses the 8KB ring end, and
; it is at the same word in every bank.  The loop runs two words a turn.
; A row is written into the slack (rule 1) or by the full write, so its order
; inside the row is free.
; -----------------------------------------------------------------------------
; one word column of a row: its %1 lines from the block, a MOVSW a bank (the
; speed pass: 18 clocks where LODSW and a store are 31 to 38), DI stepped to
; the next bank by BP and back to bank 0's next word by AX
%macro BZ_RWORD 1
    mov si, [bx]
    add si, dx
 %rep %1 - 1
    movsw
    add di, bp
 %endrep
    movsw
    sub di, ax
    inc bx
    inc bx
%endmacro
bz_row:
    cmp byte [bz_vga], 0        ; THE VGA's row is one line (130.46.3), the part's
    je .c
    inc word [bz_nrow]
    BZ_VCALL BZV_ROW
    ret
.c:
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
    shr ax, 1
    shr ax, 1
    and al, 0feh                ; AX = 2 (L0 >> 3)
    xchg ax, si                 ; (SI = R is spent: BZ_RWORD loads it)
    shl bx, 1
    add bx, [bz_mrow + si]      ; BX = the map entry of the first word
    pop cx
    mov ax, 2000h               ; the words before the ring's end
    sub ax, di
    shr ax, 1
    cmp ax, cx
    jbe .n1
    mov ax, cx
.n1:
    sub cx, ax
    push cx                     ; (the words after the wrap)
    mov cx, ax                  ; CX = the words before it (at least 1)
    mov bp, 2000h - 2           ; BP: from a bank's word to the next bank's
    cmp byte [bz_herc], 0
    mov ds, [bz_mseg]           ; DS = the course from here (MOV keeps the flags; its PICTURE part, 130.30.5)
    jne .herc
.cga:
    mov ax, 2000h               ; AX: back from bank 1 to bank 0's next word
    shr cx, 1                   ; two words a turn; an odd count enters at
    jnc .c0                     ; the pair's second half
    inc cx
    jmp short .c1
.c0:
    BZ_RWORD 2
.c1:
    BZ_RWORD 2
    loop .c0
    pop cx                      ; ...and on from the ring's start
    jcxz .out
    xor di, di
    push di                     ; (none after that)
    jmp short .cga
.herc:
    mov ax, 6000h               ; AX: back from bank 3
    shr cx, 1
    jnc .h0
    inc cx
    jmp short .h1
.h0:
    BZ_RWORD 4
.h1:
    BZ_RWORD 4
    loop .h0
    pop cx
    jcxz .out
    xor di, di
    push di
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
; bz_col - THE COLUMN WRITER (SPEC.md 130.2 rule 3): world word column AX,
; CX rows (at least 1) of the NEW window from its row BX (0 = the top: rows
; [bz_R0n]+BX ..), TOP ROW FIRST AND IN RASTER ORDER - line by line, so each
; bank's word goes out before the beam reaches it.  Written after the start
; address, from the retrace; a frame may write one column in two or three
; calls, split round the boxes (bzgame.inc bz_csplit).  DS = ours on entry.
; Preserves every register.  [bz_ncol] counts the COLUMNS (the caller).
;
; SPEC.md 130.9 item 2: the ring's WRAP ROW is found once (a column of H rows
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
; BZ_CROW and BZ_HROW are the WHEEL's too (bzwheel.inc's lane commits expand
; them with their own registers), so they stay as they were.  bz_col's own
; rows (the speed pass) are a MOVSW a bank - bz_row's BZ_RWORD - and need two
; registers set by bz_col: BP = 2000h - 2, from a bank's word to the next
; bank's, and AX = BZ_CBACK / BZ_HBACK, on to the next row's bank 0.
%macro BZ_CROWM 0
    movsw
    add di, bp
    movsw
    sub di, ax
%endmacro
%macro BZ_HROWM 0
    movsw
    add di, bp
    movsw
    add di, bp
    movsw
    add di, bp
    movsw
    sub di, ax
%endmacro
BZ_CBACK    equ 2000h + 2 - 80  ; from past bank 1's word to the next row's
BZ_HBACK    equ 6000h + 2 - 90  ; from past bank 3's
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
    shr ax, 1
    shr ax, 1
    and al, 0feh                ; AX = 2 (L0 >> 3)
    xchg ax, bx
    mov bx, [bz_mrow + bx]      ; MAP + (L0 >> 3) ROWB (130.10.4.2)
    add bx, si                  ; BX = the map entry of the first block
    pop cx                      ; CX = the rows
    mov ax, cx                  ; the first RUN: the rows before the wrap row
    cmp ax, bp
    jbe .w1
    mov ax, bp
.w1:
    sub cx, ax
    push cx                     ; (the rows after it: 0, no wrap)
    mov cx, ax                  ; CX = the run (at least 1, at most 103)
    mov bp, 2000h - 2           ; BP: from a bank's word to the next bank's
    cmp byte [bz_herc], 0
    mov ds, [bz_mseg]           ; (MOV keeps the flags; the PICTURE part, 130.30.5)
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
    mov dl, 0                   ; (ROWB read through DS = the part, 130.10.6.4)
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
    mov ax, BZ_CBACK
.cblk:
    add bx, [BZC_ROWB]          ; the next block row
    mov si, [bx]
    BZ_CROWM
    BZ_CROWM
    BZ_CROWM
    BZ_CROWM
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
    pop cx                      ; the run after the wrap row: from the ring's
    jcxz .out                   ; start
    xor ax, ax
    push ax                     ; (none after that)
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
    mov ax, BZ_HBACK
.hblk:
    add bx, [BZC_ROWB]
    mov si, [bx]
    BZ_HROWM
    BZ_HROWM
    loop .hblk
.htail:
    or dl, dl                   ; DL = 1: the run ends inside a block
    jz .hnext
    add bx, [BZC_ROWB]
    mov si, [bx]
    call .hrow
.hnext:
    pop cx                      ; the run after the wrap row
    jcxz .out
    xor ax, ax
    push ax
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
    mov ax, BZ_CBACK            ; (MOV keeps the flags)
    jb .c1
    je .c2
    BZ_CROWM
.c2:
    BZ_CROWM
.c1:
    BZ_CROWM
    ret
.hrow:                          ; one Hercules row
    mov ax, BZ_HBACK
    BZ_HROWM
    ret

; -----------------------------------------------------------------------------
; THE BOXES (SPEC.md 130.4, 130.11.10).  A box is a rectangle of the world in
; WORDS x LINES, composed in RAM from the course, the shadow, the ball's sprite
; and the occluders that lay back over them, and then written to the card a
; line at a time.  Descriptor, BZ_BOXD bytes: +0 x0 (world word column), +2 y0
; (world line), +4 w (words), +6 h (lines), +8 the buffer, +10 the overlap
; band's xhi (0: none), +12 xlo, +14 xa, +16 xb (bz_boxw), +18 the box's
; GROUP (0 the ball's, 1 the shadow's, 2 the contact's), +19 unused.  At most four boxes a
; frame (bzgame.inc bz_mkboxes).  A buffer's lines are BZ_BOXW words apart
; whatever the box's w (SPEC.md 130.9 item 1: a fixed stride is what lets the
; fill and the sprite step by a constant).  A buffer holds BZ_BOXL lines (the
; RIDE BOX and the slab's box after a waited frame, SPEC.md 130.13.4.1,
; 130.13.4.3); every union but the platform's is held to BZ_BOXH.
; -----------------------------------------------------------------------------
BZ_BOXW     equ 4               ; words (8 bytes)
BZ_BOXH     equ 24              ; lines: the union limit of every group but the platform's
BZ_BOXL     equ 32              ; lines: the platform's union limit, and a buffer's
BZ_BOXB     equ BZ_BOXW * 2 * BZ_BOXL
BZ_BOXD     equ 20
; wave 9 (SPEC.md 130.25.19): the pickup cue's LOOK, bz_clook (bz_cuef):
; bits 0-3 the sparkles' hop count mod 16 (it moves at each hop and at no
; other frame; the sprite's shift is not in it), and
BZ_CL_RI    equ 10h             ; the LIFE's RISE (SPEC.md 130.55): the places climb
BZ_CL_SP    equ 20h             ; the SPARKLES
BZ_CL_BL    equ 80h             ; a FLASH frame (BLINK4, every 4th): no ball

; bz_boxc - compose box SI (a descriptor): fill from the course, then the
; slab when it is under the ball (bz_pov 0, bzwheel.inc bz_pblit), the
; shadow when it is drawn this frame (bz_snv: AND only), then the ball's
; sprite - each clipped to the box (bz_blit).  The occluders are laid after
; every box is composed, once a frame (bz_occ), and the slab over the ball
; after them (bz_pover).  DS = ours.  Preserves all.
;
; SPEC.md 130.9 item 1, no MUL anywhere.  THE FILL runs COLUMN-MAJOR: down one
; word column the map entry changes only every 8 lines, so each block's run of
; lines is a jump into an unrolled `movsw / add di` chain - a map read a BLOCK,
; where wave 0 read one a word.
;
; THE RUNS, IN REGISTERS (the speed pass): a box is a FIRST run (from L0 to its
; block's end, cut at the box's foot), then WHOLE blocks, then a LAST run (the
; lines left, under 8).  The first and the last go through bz_frun, whose chain
; is entered at the run's length; a whole block has no entry to compute and no
; line word to add, so its loop holds the buffer's line step in BP (`add di,
; bp`, two bytes where the chain's `add di, byte 6` is three: 8 lines a block,
; 4 clocks a line at the 8088's fetch floor) and its run costs two ADDs and a
; count - where every run used to reload and store four words of bss.  DS is
; the course part from the first run to the last (ROWB is read there, as
; bz_col reads it: 130.10.6.4).
bz_boxc:
    ; STKBALANCE-OK: nine pushes at the entry, nine pops at .nob, and between
    ; them a `push si` the fill pops at .filled and the whole blocks' `push bp`
    ; (.last pops it) - balanced on every path, but the walk cannot pair them
    ; across bz_frun, whose computed jump it does not follow.
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
    mov bp, ax
    and bp, 7
    mov dx, 8
    sub dx, bp                  ; DX = the first run's lines (to the block's end)
    shl bp, 1                   ; BP = L0's line word in a block
    shr ax, 1
    shr ax, 1
    and al, 0feh                ; AX = 2 (L0 >> 3)
    xchg ax, bx
    mov bx, [bz_mrow + bx]      ; MAP + (L0 >> 3) ROWB (130.10.4.2)
    mov ax, [si]
    shl ax, 1
    add bx, ax                  ; BX = the map entry of (L0, x0)
    mov di, [si + 8]            ; DI = the buffer's first line
    mov cx, [si + 4]            ; CX = the word columns
    mov ax, [si + 6]            ; AX = the lines
    push si                     ; (the descriptor, for the slab and the sprite)
    mov ds, [bz_mseg]           ; DS = the course's (PICTURE) part until .filled
    cmp dx, ax                  ; the first run: the block's lines, cut at the
    jbe .n                      ; box's foot
    mov dx, ax
.n:
    sub ax, dx
    push ax                     ; the lines after it
    push cx
    call bz_frun
    pop ax
    pop dx
    or dx, dx
    jz .fend                    ; (the box ended in its first block)
    shl ax, 1                   ; AX = 2 w, kept: the run's way back
    sub bx, ax                  ; the next block row's entry of x0, and the
    add bx, [BZC_ROWB]          ; buffer's line under the run
    sub di, ax
    mov bp, dx
    and bp, 7
    push bp                     ; the last run's lines (0 .. 7)
    shr dx, 1
    shr dx, 1
    shr dx, 1                   ; DX = the whole blocks
    jz .last
    mov bp, BZ_BOXW * 2 - 2     ; BP = the buffer's step after a line's word
.blk:
    mov cx, ax
    shr cx, 1
.bc:
    mov si, [bx]
%rep 8
    movsw
    add di, bp
%endrep
    sub di, byte 8 * BZ_BOXW * 2 - 2    ; back up the block and on a word column
    inc bx
    inc bx
    loop .bc
    sub bx, ax
    add bx, [BZC_ROWB]
    sub di, ax
    add di, byte 8 * BZ_BOXW * 2
    dec dx
    jnz .blk
.last:
    pop dx                      ; the last run: the block's first lines
    or dx, dx
    jz .fend
    mov cx, ax
    shr cx, 1
    xor bp, bp
    call bz_frun
.fend:
    push es
    pop ds                      ; DS = ours
.filled:
    pop si
    ; --- the slab when it is UNDER the ball (SPEC.md 130.12.4.5; over it,
    ; bz_pover lays it after the occluders) ---
    cmp byte [bz_pov], 0
    jne .shadow
    call bz_pblit
.shadow:
    ; --- the shadow, AND only (SPEC.md 130.11.10.2: before the ball) ---
    cmp byte [bz_snv], 0
    je .ball
    mov ax, [bz_spy]
    mov dx, BZ_BAL_SHDROWS
    mov di, [bz_shm]
    xor bx, bx
    call bz_blit
.ball:
    ; --- the ball's sprite: mask AND, frame OR; none while it is hidden in a
    ; tube (SPEC.md 130.12.6.1) or holed out (130.14.4.3).  ONE word test for
    ; that and the pickup CUE (wave 9, SPEC.md 130.25.19): bz_hidn and
    ; bz_clook are adjacent, so a ball with neither pays what it did ---
    mov bx, [bz_sfd]
    cmp word [bz_hidn], 0
    jne .bq
.bd:
    mov ax, [bz_py]
    mov dx, BZ_BAL_ROWS
    mov di, [bz_smsk]
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
.bq:
    cmp byte [bz_hidn], 0       ; hidden: nothing
    jne .nob
    test byte [bz_clook], BZ_CL_BL
    jnz .nob                    ; a BLINK frame: the ball not drawn
    or bh, 80h                  ; the CUE's blit (bz_blit's .cwhole)
    jmp short .bd

; the cue's SPARKLES (bz_blit's .cwhole; SPEC.md 130.25.19): three, each
; HOPPING between its places round the ball (steps a b c b, bz_cuef's
; bz_spq) - eight places, BALANCED left and right (the owner's pick, OVER:
; the first set put six right of the centre and every double-time step b
; there, 83% of the sparkles' pixel-time): the four corners, a side place
; each side high and low (x = 16 the sprite's spare right column, x = -1
; its spare LEFT one where the shift has one - at s = 0 one in, the ball
; hiding a pixel), and two of them ON the ball's face - a 2 x 2 pair each, FULLY RESOLVED (the owner's,
; 15:34): for each card, place and the sprite's shift s an entry of 3 bytes
; - the byte off = 8 dy + W from the sprite's first byte whose WORD holds
; pixels x and x + 1 (x = s + dx) at its pixels j and j + 1, and the first
; line's mask for that word - so a pair in the blit is two loads and two
; XORs and no arithmetic.  W is at most 3, so the word XORed is inside the
; sprite's 5 bytes at every shift (byte 5 never touched: a 32-line buffer's
; last byte is its 4th's bottom-right ball's byte 4).  The masks, pixel j
; alone 0C0h >> 2 j in a little-endian word (a byte on past 3): the CGA both
; pixels on both lines (the ground's ink XOR 3, a pixel two bits: the second
; line's mask is the first's; ON the face XOR 1, the ball's base to its ink,
; a GLINT, where 3 would punch the ground's colour into it); the Hercules
; pixel j on the first and j + 1 on the second, which is the first's rotated
; right 2 - its grounds are a checker of whole pixels (mono pairs), where a
; 2 x 2 XORed is the checker shifted, unseen, and the diagonal is a solid
; square.  Each card has its own copy of the three pairs' code (bz_blit's
; .cwhole), drawn AFTER the ball (the face places; off the ball the result is
; the one before it would give: the mask keeps the box there and the frame is
; 0).
%define BZ_SPX(j) ((0C0h >> (2 * ((j) & 3))) << (8 * ((j) >> 2)))
BZ_SPRE     equ 3               ; an entry's bytes
BZ_SPRP     equ 4 * BZ_SPRE     ; a place's (its four shifts)
; BZ_SPR dx, dy, card (0 the CGA, 1 the Hercules), on the face (1: the CGA's
; XOR 1), and the place at a shift whose x = s + dx would be left of the
; sprite (dx = -1 at s = 0): fdx, fdy
%macro BZ_SPR 3-6 0, 0, 0
 %assign %%s 0
 %rep 4
  %assign %%dx %1
  %assign %%dy %2
  %if %%s + %%dx < 0
   %assign %%dx %5
   %assign %%dy %6
  %endif
  %assign %%x %%s + %%dx
  %assign %%b %%x >> 2
  %assign %%p %%x & 3
  %if %%p == 3
   %assign %%w %%b
   %assign %%j 3
  %elif %%b == 4
   %assign %%w 3
   %assign %%j 4 + %%p
  %else
   %assign %%w %%b
   %assign %%j %%p
  %endif
  %if %%x < 0 || %%dx > 15 || %%dy > 14 || %%w > 3 || %%j > 6
   %error "a sparkle's pair must stay inside the sprite's 5 bytes and 16 rows"
  %endif
  %if ((BZ_SPX(%%j) >> 2) | ((BZ_SPX(%%j) & 3) << 14)) != BZ_SPX(%%j + 1)
   %error "the Hercules' second line is the first's mask rotated right 2"
  %endif
            db %%dy * BZ_BOXW * 2 + %%w
  %if %3
            dw BZ_SPX(%%j)
  %elif %4
            dw (BZ_SPX(%%j) | BZ_SPX(%%j + 1)) & 5555h
  %else
            dw BZ_SPX(%%j) | BZ_SPX(%%j + 1)
  %endif
  %assign %%s %%s + 1
 %endrep
%endmacro
%macro BZ_SPRS 1                ; a card's eight places
            BZ_SPR 0, 0, %1             ; 0-2 sparkle 0's: the top left corner,
            BZ_SPR 15, 2, %1            ; the right's top, the face's lower
            BZ_SPR 4, 10, %1, 1         ; left
            BZ_SPR 14, 0, %1            ; 3-5 sparkle 1's: the top right
            BZ_SPR -1, 12, %1, 0, 0, 12 ; corner, the left's foot, the face's
            BZ_SPR 9, 4, %1, 1          ; upper right
            BZ_SPR -1, 2, %1, 0, 0, 2   ; 6-7 sparkle 2's: the left's top,
            BZ_SPR 15, 12, %1           ; the right's foot (none shared)
            BZ_SPR -1, 7, %1, 0, 0, 7   ; 8-11 the RISE's own (SPEC.md 130.55):
            BZ_SPR 15, 7, %1            ; the left's and the right's middle,
            BZ_SPR 7, 7, %1, 1          ; the face's centre and its top
            BZ_SPR 7, 0, %1, 1
%endmacro
bz_spr0:    BZ_SPRS 0
BZ_SPRC     equ $ - bz_spr0     ; a card's table
            BZ_SPRS 1
; each sparkle's steps a b c b: its places' offsets in a card's table
%define BZ_SPS(a, b, c) db (a) * BZ_SPRP, (b) * BZ_SPRP, (c) * BZ_SPRP, (b) * BZ_SPRP
bz_sps:     BZ_SPS(0, 1, 2)
            BZ_SPS(3, 4, 5)
            BZ_SPS(6, 7, 6)
; SPEC.md 130.55: the LIFE's RISE - each sparkle CLIMBS a side or the face,
; foot to top (steps a b c d, then the foot again), a step every 4 frames, the
; three a step apart (bz_spo's clocks): the left (-1, 12) (-1, 7) (-1, 2)
; (0, 0), the right (15, 12) (15, 7) (15, 2) (14, 0), the face (4, 10) (7, 7)
; (9, 4) (7, 0) - eight of its twelve places the sparkles' own
%define BZ_SPSR(a, b, c, d) db (a) * BZ_SPRP, (b) * BZ_SPRP, (c) * BZ_SPRP, (d) * BZ_SPRP
bz_spsr:    BZ_SPSR(4, 8, 6, 0)
            BZ_SPSR(7, 9, 1, 3)
            BZ_SPSR(2, 10, 5, 11)
; each mode's clocks for sparkles 1 and 2 (sparkle 0's is 0): the frames
; added before the shift - the sparkles' 5 and 2 of 8, the rise's two steps
; and one of 4
bz_spo:     db 5, 2
bz_spor:    db 8, 4
%if BZ_SPRC != 12 * BZ_SPRP || 11 * BZ_SPRP > 255
 %error "bz_sps holds a place's offset in a byte"
%endif

; bz_frun - one run of bz_boxc's fill that is not a whole block: DX lines (0 ..
; 8) of CX word columns (at least 1) from the map entry BX, the lines from
; line word BP of each block, into the buffer at ES:DI.  DS = the course part.
; -> BX past the run's entries and DI at the same word column's line under the
; run plus 2 CX (the caller takes its 2 w off both).  Clobbers AX, CX, DX, SI.
bz_frun:
    ; STKBALANCE-OK: the `jmp dx` is the entry into this routine's own
    ; unrolled chain (.chain, at the run's length), not a tail call: every
    ; entry runs on to .chend and the column loop, at the same depth, and the
    ; routine pushes nothing.  No static walk follows a computed jump into
    ; the middle of a routine (pxmaster.inc's px_quant).
    shl dx, 1
    shl dx, 1                   ; 4 bytes a chain step (the ADD's BYTE form)
    mov ax, 2
    sub ax, dx
    sub ax, dx                  ; AX = back up the run and on a word column
    neg dx
    add dx, .chend              ; DX = the chain's entry for the run
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
    sub di, ax
    inc di
    inc di                      ; DI: the line under the run (8 n on)
    ret

; bz_blit - a sprite of the ball part into box SI, clipped to it: its rows i
; at world lines AX + i, i < DX, its 5 bytes a row from world byte px / 4 (the
; ball's columns: the sprite and the shadow share them).  Row i, byte k of the
; MASK is at DI + 5 i + k in the ball part, the FRAME's BX past it (frames are
; pre-ANDed, SPEC.md 130.3) - or, BX = 0, no frame: AND only (the shadow);
; BX bit 15 set (wave 9, bz_boxc's .bq): the pickup CUE's look (bz_clook) with
; the sprite whole in the box - its sparkles and its flash - and none clipped.
; A SET mask bit keeps the box.  The whole sprite inside the box takes two
; words and a byte a row (`lodsw / and / or / stosw`), and the shadow whole
; across the same with AND alone; a sprite or a shadow clipped across, the
; byte path (clipped at the box's top or foot alone, still the word path).
; DS = ES = ours.  Preserves all but AX, BX, CX, DX, DI, BP.
bz_blit:
    cmp byte [bz_vga], 0        ; THE VGA: planar pairs at 8-pixel words, from
    je .c                       ; the converted copies (130.46.5), the part's
    BZ_VCALL BZV_BLIT
    ret
.c:
    push si
    mov bp, bx                  ; BP = the frame's distance (0: none)
    ; THE WHOLE SPRITE INSIDE THE BOX, which is what a ball's own box holds
    ; (the speed pass): three compares, the destination and no bss - where the
    ; clip below stores and reloads imin, kmin and the row's bytes for a sprite
    ; that has none to clip.  Anything else falls to the clip, with AX, DX, DI
    ; and BP as they came.
    mov bx, ax
    sub bx, [si + 2]            ; y - y0: the sprite's first line in the box
    jl .gen
    mov cx, [si + 6]
    sub cx, bx
    cmp cx, dx
    jl .gen                     ; (its foot is under the box's)
    mov cx, [bz_px]
    shr cx, 1
    shr cx, 1
    sub cx, [si]
    sub cx, [si]                ; bc - 2 x0: its first byte in the box's lines
    jl .gen
    shl bx, 1
    shl bx, 1
    shl bx, 1                   ; x 8, the buffer's stride
    add bx, cx
    add cx, BZ_BAL_RB + 1       ; bc - 2 x0 + RB <= 2 w, in words (RB is odd)
    shr cx, 1
    cmp cx, [si + 4]
    ja .gen
    add bx, [si + 8]
    mov si, di                  ; SI = the mask's row 0
    mov di, bx                  ; DI = the buffer's byte
    mov bx, bp
    or bx, bx
    js .cwhole                  ; (wave 9: the pickup CUE, BX bit 15)
    mov ds, [bz_bseg]           ; DS = the ball part from here
    jz .awhole                  ; (the shadow: DX rows, AND only)
    mov cx, dx
    jmp .wgo
    ; wave 9 (SPEC.md 130.25.19): THE PICKUP CUE, the ball whole in its box
    ; (bz_boxc's .bq: BX = the frame's distance + 8000h; DS still ours).  With
    ; the SPARKLES, THE BALL FIRST - the ordinary loop, a copy here - then
    ; three 2 x 2 pairs XORed over it (two places are on its face), each at
    ; its place's entry for the sprite's shift s (bz_spq: the place's four in
    ; the card's table, bz_cuef's): a byte offset from the sprite's first byte
    ; and the word's first line's mask (the second's the same, or on the
    ; Hercules rotated 2) - two loads and two XORs a pair, a copy for each
    ; card, no transform, no clip, no arithmetic but 3 s once.  Without them
    ; the ordinary loop.  A clipped sprite (.gen) draws no sparkles; the
    ; FLASH (BLINK4) is bz_boxc's, before any clip, so a clipped ball blinks
    ; too.
.cwhole:
    and bh, 7Fh                 ; BX = the frame's distance
    test byte [bz_clook], BZ_CL_SP
    jz .cf
    ; THE BALL FIRST - the ordinary loop, here - then
    ; the sparkles XORed over it: where a place is outside the silhouette the
    ; result is the same as before the ball (the mask keeps the box there and
    ; the frame is 0), and a place on the face XORs the ball's own pixels
    push di
    mov cx, dx                  ; (BZ_BAL_ROWS: bz_boxc's .bd's)
    mov ds, [bz_bseg]
    dec bx
    dec bx
    mov dx, BZ_BOXW * 2 - BZ_BAL_RB
.ow:
    lodsw
    and ax, [es:di]
    or ax, [bx + si]
    stosw
    lodsw
    and ax, [es:di]
    or ax, [bx + si]
    stosw
    lodsb
    and al, [es:di]
    or al, [bx + si + 1]
    stosb
    add di, dx
    loop .ow
    push es
    pop ds                      ; DS = ours
    pop di
    mov cx, [bz_px]
    and cx, 3
    mov ax, cx
    shl ax, 1
    add cx, ax                  ; CX = 3 s, the shift's entry in a place's
    xor bx, bx
    cmp byte [bz_herc], 0
    jne .sph
%macro BZ_SPK3 1                ; the three pairs: 1 the Hercules'
 %assign %%k 0
 %rep 3
    mov si, [bz_spq + 2 * %%k]  ; sparkle k's place (the card's)...
    add si, cx                  ; ...its entry for the shift
    lodsb
    mov bl, al                  ; BX = the byte
    lodsw
    xor [bx + di], ax           ; the first line's pixels...
  %if %1
    ror ax, 1                   ; (the Hercules: pixel j + 1)
    ror ax, 1
  %endif
    xor [bx + di + BZ_BOXW * 2], ax ; ...and the second's
  %assign %%k %%k + 1
 %endrep
%endmacro
    BZ_SPK3 0
    jmp short .spe
.sph:
    BZ_SPK3 1
.spe:
    jmp .out                    ; (DS is ours)
.cf:
    mov cx, dx                  ; CX = the rows
    mov ds, [bz_bseg]           ; (the flash frame draws no ball: bz_boxc's
    jmp .wgo                    ; .bq)
.gen:
    mov [bz_bly], ax
    mov [bz_blm], di
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
 %error "bz_blit's rows assume the 5-byte rows of SPEC.md 130.3"
%endif
    mov bx, bp
    mov cx, [bz_bw]
    mov ds, [bz_bseg]           ; DS = the ball part from here
    or bx, bx
    jz .andonly
    and bh, 7Fh                 ; (wave 9: a clipped sprite draws no cue)
    cmp cx, BZ_BAL_RB
    jne .clip
    mov cx, dx                  ; WHOLE ACROSS (any rows): two words and a byte a row
.wgo:
    dec bx
    dec bx                      ; (the frame's word behind SI: no displacement)
    mov dx, BZ_BOXW * 2 - BZ_BAL_RB
.whole:
    lodsw                       ; the mask (a set bit keeps the box)...
    and ax, [es:di]
    or ax, [bx + si]            ; ...and the frame, pre-ANDed (SPEC.md 130.3)
    stosw
    lodsw
    and ax, [es:di]
    or ax, [bx + si]
    stosw
    lodsb
    and al, [es:di]
    or al, [bx + si + 1]
    stosb
    add di, dx
    loop .whole
    jmp .ds
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
    jmp .ds
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
    jmp short .ds
.ds:
    push es
    pop ds                      ; DS = ours
.out:
    pop si
    ret

; AX (signed) clamped to 0 .. 255 -> AL (SPEC.md 130.15.5.1: the clamps keep
; the byte compares exact for ANY ball position).  Inline: the walk's every
; block row runs it.
%macro BZ_OCLAMP 0
    or ah, ah
    jz %%ok
    cmp ah, 80h                 ; AH 01h .. 7Fh: over 255 -> CF = 1, AL = FFh;
    sbb al, al                  ; 80h .. FFh: under 0 -> CF = 0, AL = 0
%%ok:
%endmacro

; bz_occ - THE OCCLUDER PASS (SPEC.md 130.10.8 item 1, 130.10.4.4, 130.11.10.2),
; ONCE A FRAME, after every box is composed: every record the rule lays at the
; ball's position lays its block's pixels back over the shadow and the ball in
; EVERY box it meets, `buffer = (buffer AND mask) OR (block AND NOT mask)`,
; done as `((buffer XOR block) AND mask) XOR block` - a SET mask bit keeps the
; buffer, so no NOT.  The rule, for a record (s_C, top_C):
;
;     lay it  iff  s_b < s_C  and  z_b + m < top_C
;
; s_b = [bz_sb] (bz_camera's, this frame), z_b = the integer px of bz_gz, m =
; BZ_CLIMB grounded and 0 airborne.  In RAM a record is 4 bytes (SPEC.md
; 130.15.5.1, D: 130.15.5.4 shipped it): its column, s' and t' (s_C and top_C
; biased by SB, TB and the block row) and m, its mask's MTAB index; the walk's
; keys ks and kt are the ball's side biased and clamped the same way, so the
; byte compares give the rule's verdicts.  The verdicts depend on the ball alone, so
; the NEW footprint's blocks are walked ONCE - its lines [py, py + 16) and word
; columns [nfx0, nfx1], each clipped to the window, so at most 3 x 3 blocks -
; and each laid group goes into every box that meets it (bz_olay), clipped to
; the box: two boxes that overlap hold the same bytes there.  A block row's
; records come from OCCIDX in their sorted order (column, then s_C): a binary
; search finds the first at or right of the first column - or a HINT does, the
; place the block row's last search found, proved before it is trusted - and
; the walk stops at the first right of the last.  The records of one block word are a GROUP:
; their laid masks are ANDed (bz_oand) and the word is laid ONCE a box
; (bz_olay), so a frame lays at most 3 x 3 words a box whatever the record
; counts (130.10.9).  A mask is CUMULATIVE (SPEC.md 130.11.4.2): the AND of
; every record of its block at or over it in both s' and t', and a group runs
; in (s', t') order, so only a laid record UNDER the group's least laid t' so
; far is ANDed (AH) - a ramp's rows lay one mask, not one AND a row.  Outside the footprint a box holds the course and the
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
.key:                           ; wave 10's O1: ONE BOX HOLDING THE PASS - the
    mov byte [bz_o1], 0         ; ball's, nearly always on a gated frame (no
    cmp word [bz_nbox], 1       ; shadow box, 130.11.10.2) - is laid with no
    jne .o1                     ; box loop and no clip (bz_olay): its x0 and w
    mov ax, [bz_boxes + 2]      ; and its buffer less 8 y0, once a pass
    cmp ax, [bz_olo]
    jg .o1                      ; y0 > lo
    mov bx, ax
    add bx, [bz_boxes + 6]
    cmp bx, [bz_ohi]
    jl .o1                      ; y0 + h < hi
    inc byte [bz_o1]
    shl ax, 1
    shl ax, 1
    shl ax, 1
    neg ax
    add ax, [bz_boxes + 8]
    mov [bz_obias], ax          ; buffer - 8 y0
    mov bx, [bz_boxes]
    mov bh, [bz_boxes + 4]
    mov [bz_ox0], bx            ; x0, w (bytes: a column is under 128)
.o1:
    mov ax, [bz_gz + 1]         ; the key: z_b + m
    cmp byte [bz_air], 0
    je .grd
    cmp byte [bz_ghv], 0        ; SPEC.md 130.49: a LOW FLIGHT - airborne over a
    je .air                     ; floor (bz_ghv; its h4 bz_gh), under BZ_CLIMB px
    mov bx, [bz_gh]             ; over it - takes the grounded margin, so a ball
    sar bx, 1                   ; bouncing on a ramp is not cut into the next
    sar bx, 1                   ; cell of the same ramp
    add bx, BZ_CLIMB
    cmp ax, bx
    jge .air
.grd:
    add ax, BZ_CLIMB
.air:
    mov [bz_ozkt], ax           ; THE 4-BYTE RECORD (SPEC.md 130.15.5.1): kt =
    mov ax, [bz_olo]            ; clamp(z_b + m - TB, 0, 255) - TB the BAND's
                                ; (130.51: CH, made by bz_otbk at the first block
                                ; row and again where a row starts a band) -
                                ; and the word s_b + SB - br,
                                ; unclamped, one less a block row (each row's
    and al, 0f8h                ; ks is its clamp, from its own br)
    mov [bz_obr], ax            ; the first block row's first line
    mov cl, 3
    shr ax, cl
    neg ax
    add ax, [bz_sb]
    add ax, [bz_osbias]
    mov [bz_ozk], ax
    push ds
    pop es                      ; ES = ours
    mov ds, [bz_mseg]           ; DS = the course's PICTURE part (130.30.5: occluders, map, blocks)
    call bz_otbk                 ; (CH: the first block row's band's kt)
.brow:
    mov ax, [es:bz_ozk]         ; the row's key in a register first: CL = ks =
    BZ_OCLAMP                   ; clamp(s_b + SB - br, 0, 255) from THIS row's
    mov cl, al                  ; br, never carried (SPEC.md 130.15.5.1)
    mov bx, [es:bz_obr]         ; OCCIDX[B / 8]: the row's records [SI, BP)
    shr bx, 1
    shr bx, 1
    ; THE ROW'S SUMMARY (bz_osum, made at the launch by bz_crshdr): the
    ; greatest s' and the greatest t' of ALL its records.  The rule lays a
    ; record only when ks < s' and kt < t', so a row with ks at or over its
    ; greatest s', or kt at or over its greatest t', lays nothing whatever
    ; the columns - and is left here, before its index is read.  An empty
    ; row's summary is 0, 0.  A row past the table (BZ_OSROWS) is searched.
    cmp bx, 2 * BZ_OSROWS
    jae .srow
    mov ax, [es:bz_osum + bx]
    cmp cl, al
    jae .nrow0                  ; in front of or beside every record of the row
    cmp ch, ah
    jae .nrow0                  ; over every record's top
.srow:
    mov di, bx
    add bx, [BZC_OCCIDX]
    mov si, [bx]
    mov bp, [bx + 2]
    cmp si, bp
    jae .nrow0                  ; an empty row costs one test
    ; the first record at or right of column DL.  THE HINT (the speed pass):
    ; where the same block row (mod 4) found it last time, as an offset into
    ; the row - PROVED before it is used (inside the row, on a record, the
    ; record there at or right of DL and the one before it left of DL: with the
    ; row sorted, that IS the lower bound), so a hint from another row, another
    ; course or no pass at all only costs the search it would have run anyway.
    and di, byte 6
    mov di, [es:bz_ohint + di]  ; the row's hint word
    mov ax, [es:di]
    and al, 0fch                ; (BZ_REC apart)
    add ax, si
    jc .srch
    cmp ax, bp
    ja .srch
    mov bx, ax
    je .hlo                     ; (at the row's end: every record left of DL?)
    cmp [bx], dl
    jb .srch
.hlo:
    cmp bx, si
    je .hit
    cmp [bx - BZ_REC], dl
    jae .srch
.hit:
    mov si, bx
    jmp short .bsd
.nrow0:
    jmp .nrow
.srch:
    push si                     ; a lower bound over [SI, BX), 4 bytes a
    push di                     ; record, and the hint kept for the next pass
    mov bx, bp
.bs:
    mov ax, bx
    sub ax, si
    jz .bsk
    shr ax, 1
    and ax, byte -BZ_REC        ; RECB floor(n / 2)
    mov di, si
    add di, ax                  ; DI = the middle record
    cmp [di], dl
    jae .bsh
    lea si, [di + BZ_REC]
    jmp short .bs
.bsh:
    mov bx, di
    jmp short .bs
.bsk:
    pop di
    pop ax
    neg ax
    add ax, si
    mov [es:di], ax
.bsd:
    cmp si, bp
    jae .nrow0                  ; none at or right of DL
    mov al, [si]
    cmp al, dh
    ja .nrow0                   ; the first is right of DH: none in the
.lines:                         ; footprint's columns.  The walk's keys are in
    xor di, di                  ; registers: CL = ks (.brow), CH = kt; DI = 0
    push dx                     ; until the row lays a record, then MTAB
    mov al, [si]                ; (bz_oprep).  (DL, the first column, is the
                                ; next row's)
.grp:
    mov dl, al                  ; A GROUP: the records of one block word (AL,
    xor bx, bx                  ; read once a record: the walk's and the group's
.rec:                           ; test), its laid masks ANDed - BX: 0 none laid
    cmp cl, [si + 1]            ; yet, a mask's offset, or -1 for bz_omsk
    jb .top                     ; (ks >= s', beside or in front, falls through)
.skip:
    add si, BZ_REC
    cmp si, bp
    jae .gend                   ; (the row's last group)
    mov al, [si]
    cmp al, dl
    je .rec                     ; the same block word
    or bx, bx
    jz .gnext
    call bz_olay                ; the word's lines laid ONCE a box (130.10.9)
    mov al, [si]
.gnext:
    cmp al, dh
    jbe .grp                    ; the stop: the first right of the last column
    jmp short .rdone
.gend:
    or bx, bx
    jz .rdone
    call bz_olay
.rdone:
    pop dx
.nrow:
    dec word [es:bz_ozk]        ; (the next row's br is one more)
    mov ax, [es:bz_obr]
    add ax, 8
    mov [es:bz_obr], ax
    cmp ax, [es:bz_ohi]
    jge .amod
    test al, 7fh                ; SPEC.md 130.51: a row that starts a BAND (its
    jnz .brow1                  ; first line a multiple of 128) takes its kt
    call bz_otbk
.brow1:
    jmp .brow
.amod:
    call bz_amodel              ; SPEC.md 130.29: the model, in a VOID cell
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
.top:                           ; ks < s': behind it - and under its top?
    cmp ch, [si + 2]
    jae .skip                   ; kt >= t': above it
    inc word [es:bz_nlay]       ; LAID
    or di, di
    jnz .prd
    call bz_oprep               ; the row's first: its lines, its map row, MTAB
.prd:
    or bx, bx
    jnz .and
    mov bl, [si + 3]            ; the group's first: its own mask, MTAB[m]
    xor bh, bh
    shl bx, 1
    mov bx, [bx + di]
.tmin:
    mov ah, [si + 2]            ; AH = the least t' the group has laid
    jmp short .skip
.and:                           ; a second or later.  SPEC.md 130.11.4.2: a
    cmp [si + 2], ah            ; record's mask is CUMULATIVE - the AND of
    jae .skip                   ; every record of its block at or over it in
    call bz_oand                ; both s' and t' - and the group runs in (s',
    jmp short .tmin             ; t') order, so a laid record at or over the
                                ; least t' laid is under a laid mask already

; bz_otbk - SPEC.md 130.51, 130.52: the block row bz_obr's BAND, b = line >>
; 7, from entry b of the bands' table (YOFF, bz_otb; 4 bytes an entry) in the
; PICTURE part: CH = kt = clamp(z_b + m - TB[b], 0, 255), and bz_mtab = its
; mask table (one table for every band, or a band's own under `masks
; banded`; bz_oprep's DI).  DS = the course's picture part, ES = ours.
; Clobbers AX, BX.
bz_otbk:
    mov bx, [es:bz_obr]
    shl bx, 1                   ; BH = line >> 7 (a line is under 32,768)
    mov bl, bh
    xor bh, bh
    shl bx, 1
    shl bx, 1
    add bx, [es:bz_otb]
    mov ax, [bx + 2]
    mov [es:bz_mtab], ax
    mov ax, [es:bz_ozkt]
    sub ax, [bx]
    BZ_OCLAMP
    mov ch, al
    ret

; the hints' words, by the block row mod 4: four words of bss the fill used to
; hold its run in (bzgame.inc's bz_fmp .. bz_fln, free since the speed pass)
bz_ohint:
    dw bz_fmp, bz_fbp, bz_flo, bz_fln

; bz_oprep - a block row's first LAID record: the lines of the row inside the
; footprint ([bz_of, + bz_on), bz_ofl2 = 2 x the first's place in the block),
; its map row (bz_omrow: bz_mrow[B / 8], as the fill's) and DI = MTAB.  A
; row that lays nothing never pays for them (the speed pass: 6 rows in 10 on
; MILL's demo).  DS = the course part, ES = ours.  Preserves all but AX and DI.
bz_oprep:
    push bx
    push cx
    mov ax, [es:bz_obr]         ; the block row's lines inside [lo, hi):
    mov bx, [es:bz_olo]         ; [max(lo, B), min(hi, B + 8))
    cmp bx, ax
    jge .f
    mov bx, ax
.f:
    mov [es:bz_of], bx
    mov di, bx                  ; ONE BOX HOLDING THE PASS (bz_occ's, O1; made
    shl di, 1                   ; whatever bz_o1 says): the row's word 0 in it,
    shl di, 1                   ; + 8 f
    shl di, 1
    add di, [es:bz_obias]
    mov [es:bz_orw], di
    mov di, [es:bz_ohi]
    mov cx, ax
    add cx, 8
    cmp di, cx
    jle .e
    mov di, cx
.e:
    sub di, bx
    mov [es:bz_on], di
    and bx, 7
    shl bx, 1
    mov [es:bz_ofl2], bx        ; 2 x the first line's place in the block
    shr ax, 1                   ; (B a block row's first line: 8 br)
    shr ax, 1
    xchg ax, di
    mov ax, [es:bz_mrow + di]
    mov [es:bz_omrow], ax
    mov di, [es:bz_mtab]
    pop cx
    pop bx
    ret

; bz_oand - a group's second or later laid record, SI, ANDed into bz_omsk:
; BX = the group's mask so far (a part offset, or -1 for bz_omsk already) ->
; BX = -1.  Only the lines the pass lays ([bz_ofl2 / 2, + bz_on), at the
; same place in bz_omsk as in a mask); the AND of two keep-masks keeps only
; what both keep, so laying it once is laying each in turn (130.10.8 item 1).
; The record's mask is MTAB[m] (DI = MTAB on entry), and the
; lookup comes FIRST: it uses AX, which then carries bz_ofl2 (SPEC.md
; 130.15.5.2).  DS = the course part, ES = ours.  Preserves all but AX and BX.
bz_oand:
    push cx
    push si
    push di
    mov cx, [es:bz_on]
    mov al, [si + 3]
    xor ah, ah
    shl ax, 1
    add di, ax
    mov si, [di]                ; MTAB[m]
    mov ax, [es:bz_ofl2]
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
; block: bz_ofl2), under mask BX (a part offset, or -1 for [bz_omp]: bz_omsk,
; or the model's checker, bz_amodel), each box taking the lines and the word
; it holds: buffer = ((buffer XOR block) AND mask) XOR block.  Wave 10's O1:
; a pass with ONE box holding every line of the pass (bz_o1, bz_occ's; ~96%
; of PEAK's lays) lays the word with no box loop and no clip - the column
; test, the row's word 0 in the box (bz_orw, bz_oprep's) and the lines.  DS =
; the course part, ES = ours.  Preserves all but AX and BX.
bz_olay:
    push cx
    push dx
    push si
    push di
    xor dh, dh                  ; DX = the block word
    mov si, dx
    shl si, 1
    add si, [es:bz_omrow]
    mov si, [si]                ; SI = the block (an absolute offset)
    cmp byte [es:bz_o1], 0
    je .gen
    mov ax, dx                  ; ONE BOX: 2 (c - x0), the byte compare (c and
    sub al, [es:bz_ox0]         ; x0 under 128, AH = 0: left of x0 is over
    cmp al, [es:bz_ow]          ; 128, past any w)
    jae .x
    shl ax, 1
    add ax, [es:bz_orw]
    mov di, ax                  ; DI = the buffer's word
    mov cx, [es:bz_on]          ; the row's lines, all the box's
    mov ax, [es:bz_ofl2]
    call bz_olines
.x:
    pop di
    pop si
    pop dx
    pop cx
    ret
.gen:                           ; EVERY BOX, each clipped
    push bp
    mov bp, bx                  ; BP = the mask
    mov [es:bz_oblk], si
    mov si, bz_boxes
    mov cx, [es:bz_nbox]
.box:
    push cx
    mov ax, dx                  ; the word inside the box: DI = 2 (c - x0)
    sub ax, [es:si]
    cmp ax, [es:si + 4]
    jae .nb                     ; (unsigned: left of x0 is huge)
    shl ax, 1
    mov di, ax
    mov ax, [es:bz_of]          ; the lines: [max(f, y0), min(f + n, y0 + h))
    mov cx, ax
    add cx, [es:bz_on]
    mov bx, [es:si + 2]
    cmp ax, bx
    jge .l0
    mov ax, bx
.l0:
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
    push si
    push dx
    mov si, [es:bz_oblk]
    mov bx, bp
    call bz_olines
    pop dx
    pop si
.nb:
    pop cx
    add si, BZ_BOXD
    loop .box
    pop bp
    jmp short .x

; bz_olines - bz_olay's lines: SI = the block, AX = 2 x the first line's place
; in the block, BX = the mask (a part offset, or -1 for [bz_omp]), DI = the
; buffer's word, CX lines (BZ_BOXW words apart).  DS = the course part, ES =
; ours.  Clobbers AX, BX, CX, DX, SI, DI.
bz_olines:
    add si, ax                  ; SI = the block's line
    cmp bx, byte -1
    je .scr
    add bx, ax                  ; BX = the mask's line
.line:
    lodsw                       ; the block's word, kept in DX: laid where the
    mov dx, ax                  ; mask is clear
    xor ax, [es:di]
    and ax, [bx]
    xor ax, dx
    stosw
    add di, byte BZ_BOXW * 2 - 2 ; (the buffer's step after a line's word)
    inc bx
    inc bx
    loop .line
    ret
.scr:
    mov bx, [es:bz_omp]         ; (bz_omsk, or the model's checker)
    add bx, ax
.sline:
    lodsw
    mov dx, ax
    xor ax, [es:di]
    and ax, [es:bx]
    xor ax, dx
    stosw
    add di, byte BZ_BOXW * 2 - 2
    inc bx
    inc bx
    loop .sline
    ret

; bz_amodel - SPEC.md 130.29: THE MODEL, in a VOID cell of a GF_ANA part, once
; bz_occ's walk has laid every group.  A front cell N = (wx + i, wy + d - i),
; d = 1 .. BZ_OCCDEPTH, i = 0 .. d - a FLOOR, WALL or GOAL, not OBS, not
; FL_FLOAT unless a GOAL, its highest corner H = 2 (z0 + 2 max(sx, 0) +
; 2 max(sy, 0)) (z0 QUARTER units, SPEC.md 130.48) over the key K = z_b + m
; - hides every picture pixel at or
; under its top edge, E(x) = Y + ((kr (2 d + 1) + 4) >> 3), d = x - X, right
; of its apex X and Y + ((kl (2 d + 1) + 3) >> 3), d = X - 1 - x, left of it,
; kr = 2 - sx, kl = 2 - sy (130.29.2).  Each block word of the footprint gets
; its mask (each column's first hidden line puts its pixel's bit pair into
; bz_atb[line], ORed down the lines, inverted, the checker ORed in:
; 130.15.10.1) and is laid by bz_olay under it (BX = -1, bz_omp) - laying a
; word again under a second mask lays it under the AND of the two, the block
; being the same, so the walk's groups need no change.
;
; THE CELL'S CACHE (the speed pass, SPEC.md 130.29.5).  The edges are picture
; columns and lines: they depend on the ball only through its cell V and the
; SET of front cells that count (H > K), never on the footprint.  So a frame
; computes only what changed since the last:
; - the ball's grid cell (bz_awx, bz_awy) the same as the last frame's: V and
;   its verdict are kept (bz_avp), no ROWTAB read;
; - a NEW V (bz_acptr) reads its 14 front cells once into the front table
;   bz_afl, a slot each in (d, i) order: H / 2 (8000h: not readable), X, Y,
;   the slopes byte and the SHADOWED halves: a flat half whose columns a flat
;   parent cell at d - 1 covers at or over it whenever it counts is never the
;   least in any column, so it is never computed (.cyes);
; - the count set is an interval of floor(K / 2), [bz_amaxnc, bz_aminc): the
;   highest H / 2 that does not count, the least that does (a wholly shadowed
;   cell apart).  K outside it recounts from the table (no grid byte read)
;   and drops the words.  No cell counting is the cell's TOP TEST (the
;   owner's, 2026-11-17): the same cell and the ball at or over every front
;   top is a few compares and out;
; - each footprint WORD's eight columns' least edge, and the word's least and
;   greatest, are computed the first frame the word is in the footprint
;   (bz_arange, every new word of the frame in one pass a half) and kept: 8
;   words from W0 = (Xv - 24) >> 3, which hold every footprint of a ball
;   centred in V (a footprint outside them re-bases W0).
; A frame in the same cell and count set reads no cell and computes no edge:
; it masks and lays.  DS = the course part, ES = ours, DL / DH the footprint's
; first and last word columns (bz_occ's).  Clobbers all but DS, ES (bz_occ's
; caller's are back at its .out).
bz_amodel:
    test byte [es:bz_gfl], BZ_GF_ANA
    jnz .ana
    ret
.ana:
    mov [es:bz_acol], dx        ; DL, DH: the columns
    mov ax, [es:bz_gx + 1]      ; the ball's centre cell (bz_foot's s_b's)
    mov si, [es:bz_gy + 1]
    mov cl, 4
    shr ax, cl                  ; wx
    shr si, cl                  ; wy
    cmp ax, [es:bz_awx]
    jne .look
    cmp si, [es:bz_awy]
    jne .look
    mov si, [es:bz_avp]         ; THE SAME GRID CELL: V's verdict kept
    or si, si
    jnz .pick
    ret
.look:
    mov [es:bz_awx], ax
    mov [es:bz_awy], si
    mov word [es:bz_avp], 0     ; (0: the model does not run here)
    push ds                     ; the GRID: the course's WORLD part (130.30.5;
    mov ds, [es:bz_cseg]        ; a one-part course's the same segment)
    mov bx, [es:bz_goff]        ; BX = BZG1
    mov di, ax
    add di, si                  ; s
    sub ax, si                  ; a
    mov [es:bz_aa], ax
    mov [es:bz_as], di
    sub di, [bx + BZG_SMIN]     ; r (a negative r is huge)
    cmp di, [bx + BZG_NROWS]
    jae .lno
    mov [es:bz_ar], di
    sub ax, [bx + BZG_AMIN]
    sar ax, 1                   ; k (a negative k is huge)
    cmp ax, [bx + BZG_KW]
    jae .lno
    shl di, 1
    add di, [bx + BZG_ROWTAB]
    mov si, [di]                ; ROWTAB[r]
    shl ax, 1
    shl ax, 1
    add si, ax                  ; V's four bytes
    mov al, [si + 2]
    and al, 0fh
    jz .lvoid
    cmp al, BZ_KTB              ; SPEC.md 130.49.1: a SPLIT cell - its VOID
    jb .lno                     ; pieces a bit each (bz_avm), and the model
    cmp al, BZ_KQ               ; runs where the ball's pick names one
    ja .lno                     ; (anything else: today's pass alone)
    mov [es:bz_avk], al
    mov bx, [si]                ; its records in D (this part, PLAIN)
    mov dl, 2
    cmp al, BZ_KQ
    jne .lp0
    mov dl, 4
.lp0:
    xor ah, ah
    mov cl, 1
.lp:
    test byte [bx + 2], 0fh
    jnz .lpn
    or ah, cl
.lpn:
    add bx, 4
    shl cl, 1
    dec dl
    jnz .lp
    or ah, ah
    jz .lno                     ; (no VOID piece)
    mov [es:bz_avm], ah
    jmp short .lset
.lvoid:
    test byte [si + 3], BZ_FL_OBS
    jnz .lno                     ; (a lift's shaft is OBS)
    mov byte [es:bz_avm], 0
.lset:
    mov [es:bz_avp], si
    pop ds
.pick:                          ; a split V: the model runs when the ball's
    cmp byte [es:bz_avm], 0     ; pick (bz_dpick, physics's own) is VOID
    je .run
    push ds
    push es
    pop ds
    mov al, [bz_avk]
    call bz_dpick               ; (DS = ours; SI kept)
    pop ds
    mov cl, al
    mov al, 1
    shl al, cl
    test [es:bz_avm], al
    jnz .run
    ret
.run:
    inc word [es:bz_namod]
    mov ax, [es:bz_gz + 1]      ; K = z_b + m, and floor(K / 2): H > K iff
    cmp byte [es:bz_air], 0     ; H / 2 > it (H a multiple of 2 px: quarter
    jne .air                    ; units, SPEC.md 130.48)
    add ax, BZ_CLIMB
.air:
    sar ax, 1
    mov [es:bz_akq], ax
    cmp si, [es:bz_acptr]
    jne .new
    cmp ax, [es:bz_amaxnc]
    jl .count0                  ; a front cell counts that did not
    cmp ax, [es:bz_aminc]
    jge .count0                 ; one that counted does not
    jmp .words                  ; THE SAME CELL AND COUNT SET: the cache's
.count0:
    jmp .count
.lno:
    pop ds
.no:
    ret
.new:                           ; A NEW V: its front table, and the count set
    mov dx, -1                  ; read with it, through the WORLD part.  DX:
    cmp word [es:bz_acptr], -1  ; THE NEIGHBOUR (the speed pass, SPEC.md
    je .nfull                   ; 130.29.5): a V one step in front of the
    cmp word [es:bz_axe], bz_axl ; (130.49.3: a table with extra slots is
    jne .nfull                  ; read whole)
    mov ax, [es:bz_awx]         ; table's own cell, (wx + 1, wy) or (wx, wy +
    mov bx, [es:bz_awy]         ; 1), sees that cell's rows 2 - 4 as its rows
    sub ax, [es:bz_atx]         ; 1 - 3, from i = 1 (DX = 1) or i = 0 (DX =
    sub bx, [es:bz_aty]         ; 0); -1: the table read whole
    or bx, bx
    jnz .ny
    cmp ax, 1
    jne .nfull
    mov dx, 1
    jmp short .nfull
.ny:
    cmp bx, 1
    jne .nfull
    or ax, ax
    jnz .nfull
    xor dx, dx
.nfull:
    mov ax, [es:bz_awx]         ; (the table's cell from here)
    mov [es:bz_atx], ax
    mov ax, [es:bz_awy]
    mov [es:bz_aty], ax
    mov [es:bz_acptr], si
    mov [es:bz_arue], dl        ; (FFh: read whole, the count set inline)
    push ds
    mov ds, [es:bz_cseg]
    mov bx, [es:bz_goff]
    mov ax, [bx + BZG_KW]
    mov [es:bz_akw], ax
    mov ax, [es:bz_aa]          ; Xv = 16 a + X0: the row d's X for i = 0 is
    mov cl, 4                   ; Xv - 16 d, and W0 = (Xv - 24) >> 3
    shl ax, cl
    add ax, [bx + BZG_X0]
    mov [es:bz_aan], ax
    sub ax, 24
    mov cl, 3
    sar ax, cl
    mov [es:bz_aw0], ax
    mov ax, [es:bz_as]          ; 8 s + Y0: the row d's 8 (s + d) + Y0 is
    shl ax, cl                  ; this plus 8 d
    add ax, [bx + BZG_Y0]
    mov [es:bz_ayb], ax
    mov word [es:bz_amaxnc], 8000h
    mov word [es:bz_aminc], 7fffh
    mov byte [es:bz_avld], 0
    mov word [es:bz_alcol], -1
    mov word [es:bz_axe], bz_axl ; SPEC.md 130.49.2: the extra slots, from V's
    mov al, [si + 2]            ; own FRONT pieces (keyed s + 1) when V is
    and al, 0fh                 ; split
    cmp al, BZ_KTB
    jb .nown
    test byte [si + 3], BZ_FL_FLOAT
    jnz .nown
    push dx
    mov dx, [es:bz_aan]         ; (Xv; [bz_ayb] is 8 s + Y0)
    mov ah, 1
    call bz_axcell
    pop dx
.nown:
    mov di, bz_afl              ; ES:DI: the table
    mov word [es:bz_ad], 1      ; THE FRONT CELLS: d = 1 .. BZ_OCCDEPTH
    or dx, dx
    js .drow
    ; THE NEIGHBOUR: rows 1 - 3 are the old rows 2 - 4 from i = DX (slots 2,
    ; 5, 9 on), their bytes the same cells' (X, Y, H and the slopes are the
    ; picture's).  A slot's shadows name its parents one row back at i and
    ; i - 1 - the same cells in both tables - but for the slot at the row's
    ; end that the old table's parent row had and the new one has not: i = 0
    ; loses its left shadow (DX = 1) and i = d its right (DX = 0); row 1 has
    ; no parents at all.  Then row 4 read, and the count set from the table.
    push ds
    push es
    pop ds                      ; DS = ours
    shl dx, 1
    shl dx, 1
    shl dx, 1                   ; DX = 8 i0
    mov ax, [bz_afe]            ; the old table's rows (its end: 16, 40, 72,
    sub ax, bz_afl              ; 112 bytes for 1 - 4 rows) -> the new one's
    mov si, bz_afl + 2 * BZ_AFL
    add si, dx
    mov cx, 2 * BZ_AFL / 2      ; row 1: the old row 2's [i0, i0 + 1]
    rep movsw
    mov si, bz_afl + 5 * BZ_AFL
    add si, dx
    mov cx, 3 * BZ_AFL / 2      ; row 2: the old row 3's [i0, i0 + 2]
    rep movsw
    mov si, bz_afl + 9 * BZ_AFL
    add si, dx
    mov cx, 4 * BZ_AFL / 2      ; row 3: the old row 4's [i0, i0 + 3]
    rep movsw
    mov byte [bz_afl + 7], 0    ; row 1: no shadow
    mov byte [bz_afl + BZ_AFL + 7], 0
    or dx, dx
    jz .nb0
    and byte [bz_afl + 2 * BZ_AFL + 7], 0fdh    ; i0 = 1: (2, 0) and (3, 0)
    and byte [bz_afl + 5 * BZ_AFL + 7], 0fdh    ; lose the left shadow
    jmp short .nb1
.nb0:
    and byte [bz_afl + 4 * BZ_AFL + 7], 0feh    ; i0 = 0: (2, 2) and (3, 3)
    and byte [bz_afl + 8 * BZ_AFL + 7], 0feh    ; lose the right shadow
.nb1:
    pop ds                      ; (the world part)
    cmp ax, 14 * BZ_AFL
    jne .nshort
    mov word [es:bz_ad], 4      ; all four rows: row 4 read as a full read's
    mov di, bz_afl + 9 * BZ_AFL ; is (.drow's step: 8 (s + 4) + Y0 and Xv -
    add word [es:bz_ayb], 3 * 8 ; 64)
    sub word [es:bz_aan], 3 * 16
    jmp short .drow
.nshort:                        ; fewer: the new table one row shorter
    mov di, bz_afl
    cmp ax, 5 * BZ_AFL
    jb .lst0                    ; (one row: none)
    mov di, bz_afl + 2 * BZ_AFL
    je .lst0
    mov di, bz_afl + 5 * BZ_AFL
.lst0:
    jmp .listed
.drow:
    mov bx, [es:bz_goff]
    mov ax, [es:bz_ar]
    add ax, [es:bz_ad]
    cmp ax, [bx + BZG_NROWS]
    jb .din
    jmp .listed                 ; (the rows only grow with d)
.din:
    shl ax, 1
    mov si, ax
    add si, [bx + BZG_ROWTAB]
    mov bp, [si]                ; BP = the row's first cell
    add word [es:bz_ayb], 8     ; 8 (s + d) + Y0
    sub word [es:bz_aan], 16    ; Xv - 16 d
    mov ax, [es:bz_aa]
    sub ax, [es:bz_ad]          ; a - d: N's a for i = 0
    sub ax, [bx + BZG_AMIN]
    sar ax, 1                   ; k0
    mov dx, [es:bz_aan]         ; DX = N's X, 32 more an i
    mov cx, [es:bz_ad]
    mov bx, cx
    shl bx, 1
    shl bx, 1
    shl bx, 1
    mov [es:bz_aoff], bx        ; P1 = (d - 1, i) is 8 d bytes back
    mov [es:bz_arow], di        ; (the row's first slot, and its last)
    add bx, di
    mov [es:bz_arowl], bx
    inc cx                      ; d + 1 cells, k0 .. k0 + d
.cell:
    mov word [es:di], 8000h     ; not readable (H / 2 under every key: no
                                ; pass reads the rest of its slot)
    cmp ax, [es:bz_akw]
    jae .cnext                  ; (a negative k is huge)
    mov si, ax
    shl si, 1
    shl si, 1
    add si, bp                  ; SI = N's four bytes: a FLOOR, WALL or GOAL,
    push ax                     ; not OBS, not FL_FLOAT unless a GOAL
    push cx
    mov ax, [si + 2]
    and al, 0fh
    dec al
    cmp al, 2
    jbe .cwh
    cmp al, BZ_KQ - 1
    ja .cno
    test ah, BZ_FL_FLOAT        ; SPEC.md 130.49.2: a SPLIT front cell - its
    jnz .cno                    ; slot stays unreadable (no shadow), its
    inc al                      ; pieces go to the extra slots (a FLOATING
    xor ah, ah                  ; one: passed over)
    call bz_axcell
    jmp .cno
.cwh:
    test ah, BZ_FL_OBS
    jnz .cno
    cmp al, 2
    je .cyes
    test ah, BZ_FL_FLOAT
    jnz .cno
.cyes:                          ; READABLE: X, the slopes, H / 2 = z0 +
    mov [es:di + 2], dx         ; 2 max(sx, 0) + 2 max(sy, 0) and Y = 8 (s + d)
    mov al, [si + 1]            ; + Y0 - 2 z0 (z0 quarter units, 130.48)
    mov [es:di + 6], al
    mov ah, al
    and al, 0fh                 ; (a nibble 8 - 15 is a negative slope)
    cmp al, 8
    jb .h1
    xor al, al
.h1:
    mov cl, 4
    shr ah, cl
    cmp ah, 8
    jb .h2
    xor ah, ah
.h2:
    add al, ah
    xor ah, ah
    shl ax, 1
    mov cx, ax
    mov al, [si]
    cbw
    add cx, ax
    mov [es:di], cx             ; CX = H / 2
    shl ax, 1
    neg ax
    add ax, [es:bz_ayb]
    mov [es:di + 4], ax         ; AX = Y
    ; THE SHADOWED HALVES (d >= 2): N's right half's columns [X, X + 15] are
    ; its parent P1 = (d - 1, i)'s left half's, its left half's [X - 16,
    ; X - 1] P2 = (d - 1, i - 1)'s right half's.  Both halves flat, P's edge
    ; is at or over N's in all 16 columns exactly when Y_P + 8 <= Y_N (F
    ; runs 0 .. 8 along a flat half, the two the other way round); and with
    ; H_P >= H_N, P counts whenever N does.  So that half of N is never the
    ; least in any column, and is never computed (bz_arange).
    mov byte [es:di + 7], 0
    cmp word [es:bz_ad], 1
    je .csh                     ; (row 1: its parents are not front cells)
    sub ax, 8                   ; AX = Y_N - 8: Y_P at or over it
    mov bl, [es:di + 6]         ; BL = N's slopes
    test bl, 0fh
    jnz .cl1                    ; N's right half not flat
    cmp di, [es:bz_arowl]
    je .cl1                     ; i = d: no P1
    mov si, di
    sub si, [es:bz_aoff]
    test byte [es:si + 6], 0f0h
    jnz .cl1                    ; P1's left half not flat
    cmp [es:si], cx
    jl .cl1                     ; H_P1 < H_N (or not readable)
    cmp [es:si + 4], ax
    jg .cl1
    or byte [es:di + 7], 1      ; the right half shadowed
.cl1:
    test bl, 0f0h
    jnz .csh                    ; N's left half not flat
    cmp di, [es:bz_arow]
    je .csh                     ; i = 0: no P2
    mov si, di
    sub si, [es:bz_aoff]
    sub si, BZ_AFL
    test byte [es:si + 6], 0fh
    jnz .csh                    ; P2's right half not flat
    cmp [es:si], cx
    jl .csh
    cmp [es:si + 4], ax
    jg .csh
    or byte [es:di + 7], 2      ; the left half shadowed
.csh:                           ; THE COUNT SET's interval (CX = H / 2, a cell
    cmp byte [es:di + 7], 3     ; with both halves shadowed apart)
    je .cno
    cmp cx, [es:bz_akq]
    jg .cgt
    cmp cx, [es:bz_amaxnc]
    jle .cno
    mov [es:bz_amaxnc], cx
    jmp short .cno
.cgt:
    cmp cx, [es:bz_aminc]
    jge .cno
    mov [es:bz_aminc], cx
.cno:
    pop cx
    pop ax
.cnext:
    add di, BZ_AFL
    add dx, 32
    inc ax
    dec cx
    jz .cend
    jmp .cell
.cend:
    mov ax, [es:bz_ad]
    inc ax
    mov [es:bz_ad], ax
    cmp ax, BZ_OCCDEPTH
    ja .listed
    jmp .drow
.listed:
    mov [es:bz_afe], di
    pop ds                      ; (DS = the picture part again)
    cmp byte [es:bz_arue], 0ffh
    je .lwords                  ; read whole: the count set read with it
    mov ax, [es:bz_akq]         ; a neighbour's: from the table
    jmp .count
.lwords:
    jmp .words
.count:                         ; THE COUNT SET from the table (AX = floor(K /
    mov byte [es:bz_avld], 0    ; 2)), the words dropped: BX the highest H / 2
    mov word [es:bz_alcol], -1
    mov bx, 8000h               ; at or under it, DX the least over it (a cell
    mov dx, 7fffh               ; whose halves are both left out apart; then
    mov si, [es:bz_afe]         ; the extra slots, 130.49.3)
    mov [es:bz_alim], si
    mov si, bz_afl
    jmp short .ct
.cl:
    cmp byte [es:si + 7], 3
    je .cn
    mov cx, [es:si]
    cmp cx, ax
    jg .cg
    cmp cx, bx
    jle .cn
    mov bx, cx
    jmp short .cn
.cg:
    cmp cx, dx
    jge .cn
    mov dx, cx
.cn:
    add si, BZ_AFL
.ct:
    cmp si, [es:bz_alim]
    jb .cl
    mov cx, [es:bz_axe]
    cmp cx, [es:bz_alim]
    je .cte
    mov [es:bz_alim], cx
    mov si, bz_axl
    jmp short .ct
.cte:
    mov [es:bz_amaxnc], bx
    mov [es:bz_aminc], dx
.words:
    cmp word [es:bz_aminc], 7fffh
    jne .wany
    ret                         ; none counts: nothing in front hides the ball
.wany:                          ; THE FOOTPRINT'S WORDS: the same columns as
    mov dx, [es:bz_acol]        ; the last frame's and nothing dropped since
    cmp dx, [es:bz_alcol]       ; (bz_alcol, emptied wherever bz_avld is):
    jne .wnew                   ; their slots and least edge are the last
    mov bp, [es:bz_aemin]       ; frame's
    jmp .wsame
.wnew:                          ; slots j0 .. j0 + DH - DL of the cache
    mov al, dl                  ; (re-based when outside it), the ones not
    xor ah, ah                  ; computed yet computed (bz_arange), and BP the
    sub ax, [es:bz_aw0]         ; least edge of all
    mov bl, dh
    sub bl, dl
    xor bh, bh
    add bx, ax                  ; BX = the last word's slot
    cmp ax, 7
    ja .wbase                   ; (left of W0: huge)
    cmp bx, 7
    jbe .wfit
.wbase:
    mov al, dl
    xor ah, ah
    mov [es:bz_aw0], ax
    mov byte [es:bz_avld], 0
    sub bx, ax
    xor ax, ax
.wfit:
    mov [es:bz_aj0], ax         ; (j0, for the rows)
    mov cx, ax                  ; the words not yet computed: the first's and
    mov dx, -1                  ; the last's slots (CL, DL)
    mov ch, 1
    shl ch, cl                  ; CH = j0's bit
.wl:
    test [es:bz_avld], ch
    jnz .wh
    or dl, dl
    jns .wd                     ; (one before it)
    mov dl, cl
.wd:
    mov dh, cl
.wh:
    shl ch, 1
    inc cl
    cmp cl, bl
    jbe .wl
    or dl, dl
    js .wmin                    ; every one computed
    push ax
    push bx
    mov al, dl
    mov bl, dh
    call bz_arange              ; slots AL .. BL
    pop bx
    pop ax
.wmin:
    shl ax, 1                   ; BP = the least edge over the words
    shl bx, 1
    mov si, ax
    mov bp, 7fffh
.wm:
    cmp bp, [es:bz_awlo + si]
    jle .wm1
    mov bp, [es:bz_awlo + si]
.wm1:
    inc si
    inc si
    cmp si, bx
    jbe .wm
    mov [es:bz_aemin], bp
    mov dx, [es:bz_acol]
    mov [es:bz_alcol], dx
.wsame:
    cmp bp, [es:bz_ohi]         ; a footprint whose every edge is under its
    jl .rows                    ; last line lays nothing, and is left here
    ret
.rows:                          ; THE MASKS: each block row of [olo, ohi),
    mov ax, [es:bz_olo]         ; its laid lines [rs, re) = [max(B, olo),
    and ax, 0fff8h              ; min(B + 8, ohi)) in SI and CX; a row whose
.mrow:                          ; lines are all over every edge (BP's) is
    mov [es:bz_obr], ax         ; passed by (B: bz_oprep's too)
    mov si, [es:bz_olo]
    cmp si, ax
    jge .rs
    mov si, ax
.rs:
    mov cx, ax
    add cx, 8
    cmp cx, [es:bz_ohi]
    jle .re
    mov cx, [es:bz_ohi]
.re:
    cmp bp, cx
    jl .mrw
    jmp .mrd
.mrw:
    mov [es:bz_ars], si
    mov [es:bz_are], cx
    mov di, 0                   ; DI = 0 until the row's bz_oprep has run
    mov dx, [es:bz_acol]
    mov bx, [es:bz_aj0]         ; BX = 2 j
    shl bx, 1
.mword:
    cmp [es:bz_awlo + bx], cx
    jge .mnext                  ; every edge under the laid lines: nothing
    or di, di                   ; the row's first word to lay: its lines and
    jnz .mprep                  ; map row, once (bz_oprep; DI = MTAB)
    call bz_oprep
.mprep:
    cmp [es:bz_awhi + bx], si
    jg .mpart
    mov word [es:bz_omp], bz_achk ; every edge at or over the first laid
    cmp byte [es:bz_vga], 0     ; (the VGA's checker, 130.46.5)
    je .achk
    mov word [es:bz_omp], bz_achkv
.achk:
.mlay:                          ; line: every pixel hidden, the checker alone
    push bx
    mov bx, -1
    call bz_olay                ; word DL, lines [bz_of, + bz_on)
    pop bx
.mnext:
    inc bx
    inc bx
    inc dl
    cmp dl, dh
    jbe .mword
.mrd:
    mov ax, [es:bz_obr]
    add ax, 8
    cmp ax, [es:bz_ohi]
    jge .mout
    jmp .mrow
.mout:
    mov word [es:bz_omp], bz_omsk
    ret
.mpart:                         ; SPEC.md 130.49.7: a FLAT word - its eight
    mov ax, [es:bz_awlo + bx]   ; columns' least edge one line E (a split
    cmp ax, [es:bz_awhi + bx]   ; piece's centre edge, a flat L - R diagonal):
    jne .mbuild                 ; no mask built, the lines [E, re) laid under
    push bx                     ; the checker alone - bz_oprep's lines moved
    sub ax, [es:bz_of]          ; down by E - rs for the lay and back
    push word [es:bz_of]
    push word [es:bz_on]
    push word [es:bz_ofl2]
    push word [es:bz_orw]
    add [es:bz_of], ax
    sub [es:bz_on], ax
    shl ax, 1
    add [es:bz_ofl2], ax
    shl ax, 1
    shl ax, 1
    add [es:bz_orw], ax
    mov word [es:bz_omp], bz_achk
    cmp byte [es:bz_vga], 0     ; (the VGA's checker, 130.46.5)
    je .mpc
    mov word [es:bz_omp], bz_achkv
.mpc:
    mov bx, -1
    call bz_olay
    pop word [es:bz_orw]
    pop word [es:bz_ofl2]
    pop word [es:bz_on]
    pop word [es:bz_of]
    pop bx
    jmp .mnext
.mbuild:                        ; THE WORD'S MASK over the laid lines [rs, re):
    push bx                     ; each column's first hidden line - rs (0 ..
    push dx                     ; re - rs - 1, or none) puts its pixel's bit
    push bp                     ; pair into bz_atb[it], ORed down, inverted,
    push di                     ; the checker in, into bz_omsk at rs's place
    push ds
    push es
    pop ds                      ; DS = ours
    mov ax, si                  ; (rs, kept: AX)
    mov si, bx
    shl si, 1
    shl si, 1
    shl si, 1
    add si, bz_aE               ; SI = the word's columns
    mov bp, ax                  ; BP = rs
    mov di, bz_atb
    xor ax, ax
    mov cx, 8
    rep stosw                   ; (ES = ours)
    mov di, [bz_are]
    sub di, bp                  ; DI = the lines
    mov dx, 00c0h               ; pixel 0's bit pair; ROR 2 walks 1 .. 7 (the
    cmp byte [bz_vga], 0        ; VGA's planar pair: its two bits, 8080h, ROR 1,
    je .mc8                     ; SPEC.md 130.46.5)
    mov dh, 80h
    mov dl, dh
.mc8:
    mov cx, 8
.mcol:
    lodsw
    sub ax, bp                  ; the column's first hidden line, from rs
    jge .mc0
    xor ax, ax
.mc0:
    cmp ax, di
    jae .mc1                    ; none in the laid lines
    shl ax, 1
    mov bx, ax
    or [bz_atb + bx], dx
.mc1:
    ror dx, 1
    cmp byte [bz_vga], 0
    jne .mc2
    ror dx, 1
.mc2:
    loop .mcol
    mov cx, di
    mov di, bp
    and di, 7
    shl di, 1
    add di, bz_omsk             ; ES:DI = bz_omsk's line rs
    mov dx, 3333h               ; the checker: even line 3333h, odd CCCCh (the
    cmp byte [bz_vga], 0        ; VGA's 5555h, AAAAh: the same pixels)
    je .mchk
    mov dx, 5555h
.mchk:
    test bp, 1
    jz .mev
    not dx
.mev:
    mov si, bz_atb
    xor bx, bx
.mline:
    lodsw
    or bx, ax
    mov ax, bx
    not ax
    or ax, dx
    stosw
    not dx
    loop .mline
    pop ds
    pop di
    pop bp
    pop dx
    pop bx
    mov si, [es:bz_ars]
    mov cx, [es:bz_are]
    mov word [es:bz_omp], bz_omsk
    jmp .mlay

; bz_achk - the checker alone (130.15.10.1): a word every pixel of which the
; model hides, by the line's place in its block
bz_achk:
    dw 3333h, 0cccch, 3333h, 0cccch, 3333h, 0cccch, 3333h, 0cccch
bz_achkv:                       ; ...the VGA's, as planar pairs (130.46.5)
    dw 5555h, 0aaaah, 5555h, 0aaaah, 5555h, 0aaaah, 5555h, 0aaaah

; bz_arange - bz_amodel's cache slots AL .. BL (words W0 + AL .. W0 + BL)
; computed: each column's least edge line over the COUNTING front cells (H / 2
; > floor(K / 2)), their halves the shadow test left, 7FFFh where none; then
; each word's least and greatest (bz_awlo, bz_awhi) and its bit in bz_avld.
; The slots' columns are one run (16 bytes a word), so a half meets it in one
; run of columns and is stepped along it by the formula's own increment; a
; FLAT half (its slope nibble 0, k = 2) needs no multiply: num = 4 d' + 6 on
; the right, 4 d' + 5 on the left.  DS = the part, ES = ours.  Clobbers all
; but DS, ES.
bz_arange:
    push ds
    push es
    pop ds                      ; DS = ours
    xor ah, ah
    xor bh, bh
    push ax                     ; (the first slot and the last, for the words)
    push bx
    sub bx, ax
    inc bx                      ; BX = the words
    mov cl, 4
    shl ax, cl
    add ax, bz_aE
    mov di, ax                  ; DI = the first slot's columns, every one
    mov cl, 3                   ; "none"
    shl bx, cl
    mov cx, bx                  ; CX = the columns
    mov ax, 7fffh
    rep stosw
    mov ax, [bz_aw0]            ; the slots' first column 8 W0 (bz_axb), and
    mov cl, 3                   ; the run's [x0, x1] (bz_axw, bz_axw7)
    shl ax, cl
    mov [bz_axb], ax
    pop bx                      ; (the last slot)
    pop dx                      ; (the first)
    push dx
    push bx
    shl dx, cl
    add dx, ax
    mov [bz_axw], dx
    inc bx
    shl bx, cl
    add ax, bx
    dec ax
    mov [bz_axw7], ax
    mov si, [bz_afe]            ; (the table, then the extra slots: 130.49.3)
    mov [bz_alim], si
    mov si, bz_afl
.e:
    cmp si, [bz_alim]
    jb .e1
    mov ax, [bz_axe]
    cmp ax, [bz_alim]
    je .ee
    mov [bz_alim], ax
    mov si, bz_axl
    jmp short .e
.ee:
    jmp .mm
.e1:
    mov ax, [si]
    cmp ax, [bz_akq]
    jle .en0                    ; H <= K: it does not count (or not readable)
    mov dx, [si + 2]            ; DX = X
    test byte [si + 7], 1
    jz .right
    jmp .left                   ; (the right half shadowed)
.en0:
    jmp .en
.right:                         ; THE RIGHT HALF: [max(X, x0), min(X + 15,
    mov cx, dx                  ; x1)], d' = x - X, num = kr (2 d' + 1) + 4
    cmp cx, [bz_axw]            ; (a centre ON the edge is not the top's,
    jge .r0                     ; 130.29.2), +2 kr a column, kr = 2 - sx
    mov cx, [bz_axw]
.r0:
    mov bp, dx
    add bp, 15
    cmp bp, [bz_axw7]
    jle .r1
    mov bp, [bz_axw7]
.r1:
    sub bp, cx
    jl .left
    push dx
    mov di, cx
    sub di, [bz_axb]
    shl di, 1
    add di, bz_aE               ; DI = the first column's least
    mov ax, cx
    sub ax, dx                  ; d'
    mov cx, bp
    inc cx                      ; CX = the columns
    test byte [si + 7], 8
    jnz .rx                     ; (an extra slot: its own k, 130.49.2)
    mov bl, [si + 6]
    and bl, 0fh
    jnz .rk
    shl ax, 1                   ; flat: 4 d' + 6, +4 a column
    shl ax, 1
    add ax, 6                   ; (flat: 2 (2 d' + 1) + 4)
    mov dx, 4
    jmp short .rh
.rk:
    shl ax, 1
    inc ax
    push cx
    mov cl, 4
    shl bl, cl
    sar bl, cl
    pop cx
    neg bl
    add bl, 2                   ; BL = kr
    imul bl                     ; AX = kr (2 d' + 1)
    add ax, 4                   ; (the right half's + 4)
    mov dl, bl
    xchg ax, dx
    cbw
    shl ax, 1
    xchg ax, dx                 ; DX = 2 kr
.rh:
    mov bx, [si + 4]            ; BX = Y
    call bz_ahalf
    pop dx
    jmp short .left
.rx:                            ; AN EXTRA SLOT's right half-edge: k its +6,
    shl ax, 1                   ; num = k (2 d' + 1) + 4 (apex T, / 8) or + 8
    inc ax                      ; (apex the centre, / 16), +2 k a column
    mov bl, [si + 6]
    imul bl
    mov dl, bl
    xchg ax, dx
    cbw
    shl ax, 1
    xchg ax, dx                 ; DX = 2 k
    mov bx, [si + 4]
    test byte [si + 7], 4
    jnz .rxc
    add ax, 4
    call bz_ahalf
    pop dx
    jmp short .left
.rxc:
    add ax, 8
    call bz_ahalf4
    pop dx
.left:                          ; THE LEFT HALF: [max(X - 16, x0), min(X - 1,
    test byte [si + 7], 2       ; x1)], d' = X - 1 - x, num = kl (2 d' + 1)
    jnz .en                     ; + 3, -2 kl a column (d' falls), kl = 2 - sy
    mov cx, dx
    sub cx, 16
    cmp cx, [bz_axw]
    jge .l0
    mov cx, [bz_axw]
.l0:
    mov bp, dx
    dec bp
    cmp bp, [bz_axw7]
    jle .l1
    mov bp, [bz_axw7]
.l1:
    sub bp, cx
    jl .en
    mov di, cx
    sub di, [bz_axb]
    shl di, 1
    add di, bz_aE
    mov ax, dx
    dec ax
    sub ax, cx                  ; d' = X - 1 - x
    mov cx, bp
    inc cx
    test byte [si + 7], 8
    jnz .lx
    mov bl, [si + 6]
    and bl, 0f0h
    jnz .lk
    shl ax, 1                   ; flat: 4 d' + 5, -4 a column
    shl ax, 1
    add ax, 5
    mov dx, -4
    jmp short .lh
.lk:
    shl ax, 1
    inc ax
    push cx
    mov cl, 4
    sar bl, cl
    pop cx
    neg bl
    add bl, 2                   ; BL = kl
    imul bl                     ; AX = kl (2 d' + 1)
    add ax, 3
    mov dl, bl
    xchg ax, dx
    cbw
    shl ax, 1
    neg ax
    xchg ax, dx                 ; DX = -2 kl
.lh:
    mov bx, [si + 4]
    call bz_ahalf
    jmp short .en
.lx:                            ; AN EXTRA SLOT's left half-edge: num = k (2
    shl ax, 1                   ; d' + 1) + 3 (apex T) or + 8 (the centre),
    inc ax                      ; -2 k a column
    mov bl, [si + 6]
    imul bl
    mov dl, bl
    xchg ax, dx
    cbw
    shl ax, 1
    neg ax
    xchg ax, dx                 ; DX = -2 k
    mov bx, [si + 4]
    test byte [si + 7], 4
    jnz .lxc
    add ax, 3
    call bz_ahalf
    jmp short .en
.lxc:
    add ax, 8
    call bz_ahalf4
.en:
    add si, BZ_AFL
    jmp .e
.mm:                            ; EACH WORD'S least and greatest, its bit set
    pop dx                      ; (the last slot)
    pop ax                      ; (the first)
.mw:
    push ax
    mov si, ax
    mov cl, 4
    shl si, cl
    add si, bz_aE
    mov bx, 7fffh
    mov di, 8000h
    mov cx, 8
.m:
    lodsw
    cmp ax, bx
    jge .m1
    mov bx, ax
.m1:
    cmp ax, di
    jle .m2
    mov di, ax
.m2:
    loop .m
    pop ax
    mov si, ax
    shl si, 1
    mov [bz_awlo + si], bx
    mov [bz_awhi + si], di
    mov cl, al
    mov ch, 1
    shl ch, cl
    or [bz_avld], ch
    inc ax
    cmp ax, dx
    jbe .mw
    pop ds
    ret

; bz_ahalf - E = Y + (num >> 3) over CX columns from DI (bz_aE's), num = AX
; stepping by DX a column, BX = Y: each the least of it and the column's.
; num is carried x 32, so its high byte IS num >> 3 (|num| < 1,024).  DS = ours.
; Clobbers AX, CX, DX, DI, BP.
bz_ahalf:
    push cx
    mov cl, 5
.sh:
    shl ax, cl
    shl dx, cl
    pop cx
    mov bp, ax
.c:
    mov ax, bp
    mov al, ah
    cbw
    add ax, bx
    cmp ax, [di]
    jge .k
    mov [di], ax
.k:
    add bp, dx
    inc di
    inc di
    loop .c
    ret

; bz_ahalf4 - bz_ahalf with num / 16 (SPEC.md 130.49.2's centre edge): num is
; carried x 16, so its high byte is num >> 4.
bz_ahalf4:
    push cx
    mov cl, 4
    jmp short bz_ahalf.sh

; bz_axcell - SPEC.md 130.49.2: a SPLIT cell's pieces' HALF-EDGES into the
; extra slots (bz_axl .. bz_axe): SI = the cell's four bytes (DS = the world
; part), AL its kind (4 - 6), AH nonzero for V's OWN cell (its FRONT pieces
; alone: an LR's down half, a quartered cell's E and S, keyed s + 1), DX its
; apex column X, [bz_ayb] its row's 8 s + Y0.  Each FLOOR, WALL or GOAL piece
; (z0 QUARTER units, SPEC.md 130.48): H / 2 = z0 + the greatest of its
; vertices' 0 (T), 2 sx (R), 2 (sx + sy) (B), 2 sy (L) and sx + sy (the
; centre); a slot each of its half-edges (bz_axtab), H / 2, X, Y (T: 8 s +
; Y0 - 2 z0; the centre: that + 8 - 2 (sx
; + sy)), k (T right 2 - sx, T left 2 - sy, centre right sy - sx, centre left
; sx - sy) and the flags (8 an extra slot, 4 the centre, 1 / 2 the half it is
; not); and the count set's interval (bz_akq's) as .cell's.  ES = ours.  At
; BZ_AXMAX slots it stops (the tool refuses a course that needs more).
; Preserves all.
bz_axcell:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    mov bl, al
    sub bl, BZ_KTB
    shl bl, 1
    shl bl, 1
    xor bh, bh                  ; BX = the first piece's bz_axtab entry (2 bytes)
    mov cx, 2
    cmp al, BZ_KQ
    jne .n
    mov cl, 4
.n:
    mov [es:bz_axx], dx
    mov [es:bz_axo], ah         ; (V's own: kept, AH is the loop's)
    mov si, [si]                ; SI = its records in D
    mov di, [es:bz_axe]
.p:
    push cx
    mov al, [si + 2]
    and al, 0fh
    dec al
    cmp al, 2
    ja .pn                      ; (VOID: nothing)
    mov al, [es:bz_axtab + bx + 1]
    cmp byte [es:bz_axo], 0
    je .pall
    test al, 80h
    jz .pn                      ; V's own: front pieces alone
.pall:
    mov [es:bz_axed], al
    mov al, [si + 1]            ; sx, sy (signed nibbles) -> CL, CH
    mov cl, 4
    mov ch, al
    shl al, cl
    sar al, cl
    sar ch, cl
    mov cl, al
    mov al, [es:bz_axtab + bx]  ; the vertices: T 1, R 2, B 4, L 8, C 16 -
    xor dl, dl                  ; in QUARTER units over z0 (SPEC.md 130.48):
    test al, 2                  ; T 0, R 2 sx, B 2 (sx + sy), L 2 sy, the
    jz .v1                      ; centre sx + sy; DL = the greatest (T: 0)
    cmp cl, dl
    jle .v1
    mov dl, cl
.v1:
    mov dh, cl
    add dh, ch                  ; DH = sx + sy
    test al, 4
    jz .v2
    cmp dh, dl
    jle .v2
    mov dl, dh
.v2:
    test al, 8
    jz .v3
    cmp ch, dl
    jle .v3
    mov dl, ch
.v3:
    shl dl, 1                   ; (T, R, B, L: twice the half-unit greatest)
    test al, 16
    jz .v4
    cmp dh, dl
    jle .v4
    mov dl, dh                  ; the centre: sx + sy
.v4:
    mov al, dl
    cbw
    mov bp, ax
    mov al, [si]
    cbw
    add bp, ax                  ; BP = H / 2
    shl ax, 1
    neg ax
    add ax, [es:bz_ayb]         ; AX = Y (apex T): 8 s + Y0 - 2 z0
    mov dl, 1                   ; the half-edges, a bit each: LT 1, RT 2,
.e:                             ; LC 4, RC 8
    test [es:bz_axed], dl
    jz .en
    cmp di, bz_axl + BZ_AFL * BZ_AXMAX
    jae .en
    push bx
    mov [es:di], bp             ; H / 2
    mov bx, [es:bz_axx]
    mov [es:di + 2], bx         ; X
    mov bx, ax
    test dl, 0ch
    jz .et
    push ax                     ; a centre edge: Y + 8 - 2 (sx + sy)
    mov al, dh
    cbw
    shl ax, 1
    sub bx, ax
    add bx, 8
    pop ax
.et:
    mov [es:di + 4], bx         ; Y
    mov bh, 9                   ; k and the flags: LT 2 - sy ...
    mov bl, 2
    sub bl, ch
    cmp dl, 1
    je .ek
    mov bh, 0ah                 ; ... RT 2 - sx ...
    mov bl, 2
    sub bl, cl
    cmp dl, 2
    je .ek
    mov bh, 0dh                 ; ... LC sx - sy ...
    mov bl, cl
    sub bl, ch
    cmp dl, 4
    je .ek
    mov bh, 0eh                 ; ... RC sy - sx
    mov bl, ch
    sub bl, cl
.ek:
    mov [es:di + 6], bx
    pop bx
    add di, BZ_AFL
    cmp bp, [es:bz_akq]         ; the count set's interval, as .cell's
    jg .egt
    cmp bp, [es:bz_amaxnc]
    jle .en
    mov [es:bz_amaxnc], bp
    jmp short .en
.egt:
    cmp bp, [es:bz_aminc]
    jge .en
    mov [es:bz_aminc], bp
.en:
    shl dl, 1
    cmp dl, 16
    jb .e
.pn:
    pop cx
    add si, 4
    add bx, 2
    dec cx
    jz .pd
    jmp .p
.pd:
    mov [es:bz_axe], di
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; bz_axtab - a piece's vertices (T 1, R 2, B 4, L 8, the centre 16) and its
; half-edges (LT 1, RT 2, LC 4, RC 8; 80h a FRONT piece), by its kind's base
; (TB 0, LR 2, QUARTERED 4) plus its index in D (130.24.6.1, 130.49.2)
bz_axtab:
    db 0dh, 01h, 07h, 02h               ; TB: A (T, B, L), B (T, R, B)
    db 0bh, 03h, 0eh, 8ch               ; LR: A up (T, R, L), B down (R, B, L)
    db 13h, 02h, 16h, 88h, 1ch, 84h, 19h, 01h   ; N, E, S, W

; bz_boxw - box SI (a descriptor) to the card, a line at a time, each line
; split where it crosses the ring's 8KB end.  DS = ours.  Preserves all.
; The LATER of two boxes of one group skips their overlap (SPEC.md 130.9 item
; 5, 130.11.10.2): its lines in the band (xlo, xhi] of lines-left counts write
; only the words left of [xa, xb) and right of it - the earlier box already
; put those bytes there, the same bytes.  bz_mkboxes sets the band in the
; descriptor (+10 .. +16); xhi = 0 is none.
;
; THE WHOLE-ROW PATH (SPEC.md 130.13.4.4): a box with no band, 3 or 4 words
; wide, writes each card row it covers from the row's FIRST line by an
; unrolled block - the CGA's two lines, the Hercules' four, `movsw` x w a
; line, the bank's step folded into an `add di` and the buffer's (2 bytes a
; line for a 3-word box) into `inc si` - the ring's end tested once a card
; row, as the per-line loop does (a crossing row goes to bz_wseg).  A row the
; box starts or ends inside, and any other width, take the per-line loop.
bz_boxw:
    cmp byte [bz_vga], 0        ; THE VGA: even bytes to plane 0, odd to plane 1
    je .c                       ; (130.46.5), the part's
    BZ_VCALL BZV_BOXW
    ret
.c:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    push es
    mov es, [bz_vseg]
    mov bp, [si + 6]            ; BP = lines left
    mov ax, [si + 2]            ; the first line L
    mov cl, [bz_lsh]
    mov bx, ax
    shr ax, cl                  ; R = L >> lsh
    call bz_rbR
    mov dx, [si]
    shl dx, 1
    add dx, ax
    and dh, 1fh                 ; DX = the line's offset in its bank
    mov cx, [bz_rl]
    dec cx
    and bx, cx                  ; L & (rl-1), under 8 ...
    ror bx, 1
    ror bx, 1
    ror bx, 1                   ; ... x 2000h: BX = the bank
    mov ax, [si + 4]
    mov [bz_bw], ax
    mov cx, [si + 10]           ; the band (0: none), read before SI is the
    mov di, si                  ; buffer
    mov si, [si + 8]            ; SI = the buffer
    jcxz .nob
    mov [bz_xact], cx           ; the band, copied
    mov ax, [di + 12]
    mov [bz_xlo], ax
    mov ax, [di + 14]
    mov [bz_xa], ax
    mov ax, [di + 16]
    mov [bz_xb], ax
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
.nob:                           ; no band (AX = w): every line whole.  The
    shl ax, 1                   ; buffer's step from a line's end to the next
    neg ax                      ; line's start (8 - 2w: 0 for a 4-word box)
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

; bz_bwrows - bz_boxw's WHOLE-ROW PATH (SPEC.md 130.13.4.4): from DX, the
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
